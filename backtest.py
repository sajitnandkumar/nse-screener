"""
Walk-forward backtest — reversal/break + forward-return model (Slice 26).

At each historical AS-OF date, if price is within proximity of a hull line, a setup
fires (Support/Resistance Reversal). Honest by construction: the line is detected only
on data up to the as-of date (no lookahead). Looking forward we record:

  - OUTCOME: reversed vs broke. BROKE = a close pushes > break_buffer_atr past the line
    on the wrong side (support closed below / resistance closed above) within
    classify_window bars. Otherwise REVERSED (the line held and price turned).
  - RETURNS: the signed CLOSE-to-close % move at each return_bars horizon (+ = price up).

So per category we can say: of N support reversals, X% reversed / Y% broke down, and the
average/median price move at +1 / +5 / +14 candles for each group. Reversal setups only
(v1). Writes backtest_results.json. Run: python backtest.py [sample_n]
"""

import json
import os
import sys
from datetime import datetime

import db
from atr import atr
from hull_lines import detect_hull_lines
from resample import to_weekly, to_monthly
from screener import _fit_atr, _conf_components, _label_side_sign, _turnover_cr
from settings import CFG

RESULTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_results.json")
TFS = [("1d", None), ("1w", to_weekly), ("1m", to_monthly)]


def _forward(rows, t, ret_bars, buf_price, win, side, slope, val_t):
    """Return (rets, break_bar): signed close-to-close % at each ret_bars horizon, and
    the offset of the first wrong-side break within `win` (None if it never breaks)."""
    close_t, n = rows[t][4], len(rows)
    rets = [round(100.0 * (rows[min(n - 1, t + k)][4] / close_t - 1.0), 2) for k in ret_bars]
    brk, end = None, min(n - 1, t + win)
    for i in range(t + 1, end + 1):
        lv = val_t + slope * (i - t)
        wrong = (lv - rows[i][4]) if side == "support" else (rows[i][4] - lv)
        if wrong > buf_price:
            brk = i - t
            break
    return rets, brk


def _backtest_symbol_tf(symbol, rows, tf, cfg, turnover):
    prox = cfg["proximity_atr"]
    step, min_hist = cfg["step_bars"][tf], cfg["min_history"][tf]
    ret_bars, win, buf = cfg["return_bars"], cfg["classify_window"], cfg["break_buffer_atr"]
    max_fwd = max(max(ret_bars), win)
    atr_win, on_line = CFG["hull"]["atr_window"], CFG.get("on_line_atr", 0.0)
    out, last = [], {}                      # last[side] -> as-of idx (non-overlap)

    for t in range(min_hist, len(rows) - max_fwd, step):
        sub = rows[:t + 1]
        atrv = atr(sub, atr_win)
        if not atrv:
            continue
        lines = detect_hull_lines(sub, tf)      # AS-OF detection (no lookahead)
        if not lines:
            continue
        close = sub[-1][4]

        near = {}                               # best reversal setup per side that price is at
        for ln in lines:
            dist = (close - ln["value_now"]) / atrv
            if abs(dist) > prox:
                continue
            setup = _label_side_sign(ln["side"], dist, on_line)
            if setup not in ("Support Reversal", "Resistance Reversal"):
                continue
            fit = _fit_atr(ln, atrv)
            td = [tp["date"] for tp in ln["touch_points"]]
            span_days = (datetime.strptime(max(td), "%Y-%m-%d") - datetime.strptime(min(td), "%Y-%m-%d")).days
            days_since = (datetime.strptime(sub[-1][0][:10], "%Y-%m-%d") - datetime.strptime(ln["last_touch_date"], "%Y-%m-%d")).days
            conf = _conf_components(ln["touch_count"], fit, span_days, days_since)["conf"]
            cand = {"ln": ln, "setup": setup, "conf": conf, "dist": round(dist, 2)}
            if ln["side"] not in near or conf > near[ln["side"]]["conf"]:
                near[ln["side"]] = cand

        for side, cand in near.items():
            if side in last and t - last[side] < max_fwd:
                continue
            ln = cand["ln"]
            rets, brk = _forward(rows, t, ret_bars, buf * atrv, win, side, ln["slope"], ln["value_now"])
            last[side] = t
            out.append({
                "symbol": symbol, "timeframe": tf, "setup": cand["setup"], "side": side,
                "line_type": ln["line_type"], "touches": ln["touch_count"], "conf": cand["conf"],
                "as_of_date": sub[-1][0][:10], "dist_atr": cand["dist"],
                "turnover_cr": round(turnover, 2) if turnover else None,
                "reversed": brk is None, "break_bar": brk, "rets": rets,
                # geometry for the drill-down chart (indices into the FULL series)
                "slope": ln["slope"], "value_now": ln["value_now"],
                "first_idx": ln["first_anchor_idx"], "last_idx": t,
            })
    return out


def run(sample_n=None):
    cfg = CFG["backtest"]
    min_turnover = CFG["reliability"]["min_turnover_cr"]
    turnover_lb = CFG["reliability"]["turnover_lookback"]
    results, tested = [], 0
    for symbol in db.list_symbols():
        daily = db.read_candles(symbol)
        turnover = _turnover_cr(daily, turnover_lb)
        if turnover is None or turnover < min_turnover:
            continue
        tested += 1
        if sample_n and tested > sample_n:
            break
        for tf, rs in TFS:
            rows = rs(daily) if rs else daily
            results += _backtest_symbol_tf(symbol, rows, tf, cfg, turnover)
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f)
    _summary(results, tested)
    return results


def _summary(results, tested):
    from collections import Counter
    n = len(results)
    if not n:
        print("No instances produced."); return
    rb = CFG["backtest"]["return_bars"]
    dates = [r["as_of_date"] for r in results]
    print(f"\nBACKTEST: {n} instances across {tested} liquid symbols | {min(dates)} -> {max(dates)}")
    print("by timeframe:", dict(Counter(r["timeframe"] for r in results)))

    def avg(xs):
        return sum(xs) / len(xs) if xs else 0.0

    for setup in ("Support Reversal", "Resistance Reversal"):
        s = [r for r in results if r["setup"] == setup]
        if not s:
            continue
        rev = [r for r in s if r["reversed"]]
        brk = [r for r in s if not r["reversed"]]
        print(f"\n{setup}: {len(s)} setups | reversed {100*len(rev)/len(s):.0f}% · broke {100*len(brk)/len(s):.0f}%")
        for lab, grp in (("reversed", rev), ("broke   ", brk), ("ALL     ", s)):
            if grp:
                rets = "  ".join(f"+{avg([r['rets'][i] for r in grp]):.1f}%" if avg([r['rets'][i] for r in grp]) >= 0
                                 else f"{avg([r['rets'][i] for r in grp]):.1f}%" for i in range(len(rb)))
                print(f"   {lab} n={len(grp):<6} avg move @{'/'.join(map(str, rb))}: {rets}")


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else None)
