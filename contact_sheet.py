"""
Render a contact sheet: the cleanest ranked setups as small CLOSE-price charts,
each with its detected line + touch points drawn, so the lines can be eyeballed.

Usage:  python contact_sheet.py [output.png]

EIDPARRY 1M (gold standard) and GRASIM 1d are always included and annotated with
their pass/reject status, per the acceptance test.
"""

import sys
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import db
import screener
from atr import atr
from resample import to_weekly, to_monthly
from settings import CFG
from trendlines import detect_clean_lines

_RESAMPLE = {"1d": None, "1w": to_weekly, "1m": to_monthly}


def _rows(symbol, tf):
    daily = db.read_candles(symbol)
    rs = _RESAMPLE[tf]
    return rs(daily) if rs else daily


def _line_from(cand):
    """(x0,y0,x1,y1) endpoints for the detected line, in bar-index space."""
    x0, x1 = cand["first_idx"], cand["last_idx"]
    vn, slope = cand["value_now"], cand["slope"]
    y0 = vn + slope * (x0 - x1)
    return x0, y0, x1, vn


def _forced_panel(symbol, tf):
    """Best line for a forced symbol, annotated CLEAN / not-near / REJECTED."""
    rows = _rows(symbol, tf)
    atrv = atr(rows)
    p = CFG["timeframes"][tf]
    prox = CFG["proximity_tol_atr"]
    close = rows[-1][4]

    strict = detect_clean_lines(rows, atrv, p["pivot_window"], p["min_span_bars"], strict=True)
    near = [l for l in strict if abs((close - l["value_now"]) / atrv) <= prox]
    if near:
        ln = min(near, key=lambda l: l["fit_atr"])
        status, color = "CLEAN (flagged)", "#2ea06a"
    elif strict:
        ln = min(strict, key=lambda l: l["fit_atr"])
        d = (close - ln["value_now"]) / atrv
        status, color = f"clean but {d:+.1f} ATR away (not flagged)", "#c9a227"
    else:
        loose = detect_clean_lines(rows, atrv, p["pivot_window"], p["min_span_bars"], strict=False)
        if not loose:
            return None
        ln = min(loose, key=lambda l: abs(close - l["value_now"]))
        status, color = f"REJECTED (fit={ln['fit_atr']}, viol={ln['violations']})", "#e0554e"

    return {"symbol": symbol, "tf": tf, "rows": rows, "line": ln,
            "status": status, "color": color}


def _panel_from_cand(c):
    return {"symbol": c["symbol"], "tf": c["timeframe"], "rows": _rows(c["symbol"], c["timeframe"]),
            "line": c, "status": f"{c['setup']}", "color": "#2ea06a"}


def render(path):
    symbols = db.list_symbols()
    s2r = {s: db.read_candles(s) for s in symbols}
    ranked = screener.screen_clean(s2r)
    print(f"Clean setups found across {len(symbols)} stocks x 3 TFs: {len(ranked)}")

    panels = []
    seen = set()
    # Forced acceptance-test panels first.
    for sym, tf in [("EIDPARRY-EQ", "1m"), ("GRASIM-EQ", "1d")]:
        fp = _forced_panel(sym, tf)
        if fp:
            panels.append(fp)
            seen.add((sym, tf))

    for c in ranked:
        key = (c["symbol"], c["timeframe"])
        if key in seen:
            continue
        seen.add(key)
        panels.append(_panel_from_cand(c))
        if len(panels) >= CFG["top_n"] + 2:
            break

    cols = 4
    rows_n = math.ceil(len(panels) / cols)
    fig, axes = plt.subplots(rows_n, cols, figsize=(cols * 3.4, rows_n * 2.5))
    fig.patch.set_facecolor("#0b0e13")
    axes = axes.flatten() if hasattr(axes, "flatten") else [axes]

    for ax in axes:
        ax.set_facecolor("#0b0e13")
        ax.axis("off")

    for ax, panel in zip(axes, panels):
        ax.axis("on")
        rows = panel["rows"]; ln = panel["line"]
        closes = [r[4] for r in rows]
        x = range(len(closes))
        ax.plot(x, closes, color="#8a95a3", linewidth=0.8)

        x0, y0, x1, y1 = _line_from(ln)
        ax.plot([x0, x1], [y0, y1], color=panel["color"], linewidth=1.6)
        for tp in ln["touch_points"]:
            ax.plot(tp["idx"], tp["price"], "o", color="#d6dee8", markersize=3)

        sym = panel["symbol"].replace("-EQ", "")
        lt = ln.get("line_type", "?")
        ax.set_title(f"{sym} {panel['tf']} · {lt} · fit={ln['fit_atr']} t={ln['touches']} v={ln['violations']}\n{panel['status']}",
                     color=panel["color"], fontsize=7.5, fontfamily="monospace")
        ax.tick_params(colors="#5b6570", labelsize=5)
        for s in ax.spines.values():
            s.set_color("#232b36")

    fig.tight_layout()
    fig.savefig(path, dpi=130, facecolor=fig.get_facecolor())
    print(f"Wrote {path} with {len(panels)} panels.")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "contact_sheet.png"
    render(out)
