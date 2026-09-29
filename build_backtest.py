"""
Build the backtest summary page + data into ./site (reversal/return model).

Writes:
  site/backtest.html, backtest.js, ui.css, vendor/     (frontend)
  site/data/backtest.json                                  (compact per-instance records)
  site/data/ohlcv/<SYMBOL>__<tf>.json                      (candles for the drill-down)
  backtest_summary.json (repo root, small, COMMITTED)      (per category x tf x CONF band
                                                            reversed% + avg move, for the screener)

Run after backtest.py:  python build_backtest.py
"""

import json
import os
import re
import shutil

import db
from resample import to_weekly, to_monthly
from settings import CFG

SITE = "site"
DATA = os.path.join(SITE, "data")
OHLCV = os.path.join(DATA, "ohlcv")
RESULTS = "backtest_results.json"
RESAMPLE = {"1d": None, "1w": to_weekly, "1m": to_monthly}
BANDS = [["<70", 0, 70], ["70-79", 70, 80], ["80-84", 80, 85], ["85-100", 85, 101]]
CATS = ["Support Reversal", "Resistance Reversal"]


def _safe(name):
    return re.sub(r"[^A-Za-z0-9]", "_", name)


def _grp(rows, ret_bars):
    """Aggregate a set of instances: n, reversed%, and avg move at each horizon."""
    n = len(rows)
    if not n:
        return {"n": 0, "rev": None, "move": [None] * len(ret_bars)}
    rev = round(100 * sum(1 for r in rows if r["reversed"]) / n, 1)
    move = [round(sum(r["rets"][i] for r in rows) / n, 2) for i in range(len(ret_bars))]
    return {"n": n, "rev": rev, "move": move}


def _write_summary(recs, cfg):
    """Small per (category x timeframe x CONF band) table for the screener: reversed%
    and avg move at each horizon. Committed so the deployed screener can surface it."""
    rb = cfg["return_bars"]
    cat = {}
    for c in CATS:
        crows = [r for r in recs if r["setup"] == c]
        cat[c] = {tf: {lab: _grp([r for r in crows if r["timeframe"] == tf and lo <= r["conf"] < hi], rb)
                       for lab, lo, hi in BANDS} for tf in ["1d", "1w", "1m"]}
    summary = {"ret_bars": rb, "bands": BANDS, "cat": cat,
               "overall": {c: _grp([r for r in recs if r["setup"] == c], rb) for c in CATS},
               "dmin": min(r["as_of_date"] for r in recs), "dmax": max(r["as_of_date"] for r in recs)}
    with open("backtest_summary.json", "w") as f:
        json.dump(summary, f)


def main():
    recs = json.load(open(RESULTS))
    cfg = CFG["backtest"]

    rows = [{"sym": r["symbol"], "tf": r["timeframe"], "su": r["setup"], "sd": r["side"],
             "lt": r["line_type"], "c": r["conf"], "tc": r["touches"], "dt": r["as_of_date"],
             "rev": 1 if r["reversed"] else 0, "bb": r["break_bar"], "rets": r["rets"],
             "fi": r["first_idx"], "li": r["last_idx"], "sl": r["slope"], "vn": r["value_now"]}
            for r in recs]

    os.makedirs(OHLCV, exist_ok=True)
    meta = {"ret_bars": cfg["return_bars"], "break_buffer_atr": cfg["break_buffer_atr"],
            "classify_window": cfg["classify_window"], "bands": BANDS, "cats": CATS,
            "n": len(rows), "dmin": min(r["dt"] for r in rows), "dmax": max(r["dt"] for r in rows)}
    with open(os.path.join(DATA, "backtest.json"), "w") as f:
        json.dump({"meta": meta, "rows": rows}, f)
    _write_summary(recs, cfg)

    by_sym = {}
    for r in recs:
        by_sym.setdefault(r["symbol"], set()).add(r["timeframe"])
    n_files = 0
    for symbol, tfs in by_sym.items():
        daily = db.read_candles(symbol)
        for tf in tfs:
            series = RESAMPLE[tf](daily) if RESAMPLE[tf] else daily
            candles = [{"time": x[0][:10], "open": x[1], "high": x[2], "low": x[3], "close": x[4]} for x in series]
            with open(os.path.join(OHLCV, f"{_safe(symbol)}__{tf}.json"), "w") as f:
                json.dump(candles, f)
            n_files += 1

    for name in ("backtest.html", "backtest.js", "ui.css"):
        shutil.copy(os.path.join("static", name), os.path.join(SITE, name))
    shutil.copytree(os.path.join("static", "vendor"), os.path.join(SITE, "vendor"), dirs_exist_ok=True)

    size = os.path.getsize(os.path.join(DATA, "backtest.json")) / 1e6
    print(f"backtest.json: {len(rows)} rows ({size:.1f} MB) · {n_files} candle files · page at site/backtest.html")


if __name__ == "__main__":
    main()
