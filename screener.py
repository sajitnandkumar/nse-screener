"""
The screening engine — hull-based (Slice 22 rewrite).

Lines come from hull_lines.detect_hull_lines: lower-hull edges = support,
upper-hull edges = resistance, on CLOSING prices. Between a line's anchors no
close is ever on the wrong side (true by construction, not by filtering), and a
line is kept only if tested >= min_touches and touched within recency_days.

This module adds the tradeability layer on top of that clean geometry:
  - a LIQUIDITY gate (average daily traded value) so illiquid noise is dropped,
  - the setup LABEL (side + where price sits now),
  - VOLUME context, and a touch-count-led CONFIDENCE used for ranking.

Four setups (side of the line + which side price is on now):
  - Support Reversal    : price at / above a support line   (may bounce)
  - Support Breakdown   : price has closed below a support line
  - Resistance Reversal : price at / below a resistance line (may reject)
  - Resistance Breakout : price has closed above a resistance line
"At the line" (within on_line_atr) counts as a Reversal, not a break.
"""

import json
import os
from datetime import datetime

from atr import atr
from hull_lines import detect_hull_lines
from resample import to_weekly, to_monthly
from settings import CFG

# Screening ~2000 stocks x 3 timeframes takes minutes, so we compute it once
# (after a data load) and cache the ranked setups to disk. The web app reads
# this file instantly instead of recomputing on every session.
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screen_cache.json")


def build_cache(symbol_to_rows=None):
    """Run the full screen and write the ranked setups to CACHE_FILE. Returns count."""
    import db
    if symbol_to_rows is None:
        symbol_to_rows = {s: db.read_candles(s) for s in db.list_symbols()}
    candidates = screen_clean(symbol_to_rows)
    with open(CACHE_FILE, "w") as f:
        json.dump(candidates, f)
    return len(candidates)


def load_cache():
    """Return cached setups, or None if the cache file doesn't exist yet."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)
    return None


def _label_side_sign(role, signed_dist, on_line=0.0):
    """Label from (line side) + (sign of signed_dist), in ATR. Positive = price
    above the line. Within `on_line` ATR of the line -> a Reversal (sitting on the
    line, not decisively past it)."""
    if abs(signed_dist) <= on_line:
        return "Support Reversal" if role == "support" else "Resistance Reversal"
    above = signed_dist >= 0
    if role == "support":
        return "Support Reversal" if above else "Support Breakdown"
    return "Resistance Breakout" if above else "Resistance Reversal"


def _turnover_cr(daily, lookback):
    """Average daily traded value (close x volume), in rupees crore, over the last
    `lookback` daily bars. None if there's no usable volume. Liquidity is a stock
    property, so it's measured on DAILY data regardless of the timeframe."""
    if not daily:
        return None
    tail = daily[-lookback:]
    vals = [r[4] * r[5] for r in tail if r[4] and r[5]]
    if not vals:
        return None
    return (sum(vals) / len(vals)) / 1e7    # 1 crore = 1e7


def _vol_ratio(rows, recent_bars, base_bars):
    """Recent volume expansion: MAX volume over the last `recent_bars` bars over the
    mean of the `base_bars` before them (MAX is robust to a partial current bar).
    None if there aren't enough bars."""
    if len(rows) < recent_bars + 5:
        return None
    recent = max((r[5] or 0) for r in rows[-recent_bars:])
    base_slice = rows[-(recent_bars + base_bars):-recent_bars]
    base_vols = [r[5] for r in base_slice if r[5]]
    if not base_vols:
        return None
    base = sum(base_vols) / len(base_vols)
    return recent / base if base > 0 else None


def _fit_atr(ln, atrv):
    """Average distance of the line's touches to the line, in ATR. Small by
    construction (touches are within touch_tol); used only as a ranking tie-break
    so lines whose closes sit exactly on the line edge out looser ones."""
    s, vn, last = ln["slope"], ln["value_now"], ln["last_idx"]
    ds = [abs(tp["price"] - (vn + s * (tp["idx"] - last))) for tp in ln["touch_points"]]
    return (sum(ds) / len(ds)) / atrv if ds and atrv else 0.0


def _conf_components(touches, fit_atr, span_days, days_since):
    """CONF = a transparent line-QUALITY score (0-100): "how good and proven is this
    line", NOT a trade prediction. Four independent, normalized (0-1) components,
    weighted per config. Proximity (dist_atr) and volume are deliberately EXCLUDED
    — they stay as their own columns.

        touch_score   = min(touches, touch_cap) / touch_cap      (tested a lot)
        fit_score     = 1 - min(fit_atr / fit_cap, 1)            (tighter hug)
        span_score    = min(span_days / span_cap_days, 1)        (long-established)
        recency_score = linear decay of days_since over recency_window (still live)

    span is in CALENDAR DAYS (uniform across timeframes — a 2-year line scores the
    same whether daily, weekly or monthly). Returns the four sub-scores + CONF."""
    c = CFG["confidence"]
    touch = min(touches, c["touch_cap"]) / c["touch_cap"]
    fit = 1.0 - min(fit_atr / c["fit_cap"], 1.0)
    span = min(span_days / c["span_cap_days"], 1.0)
    rw = c["recency_window"]
    recency = max(0.0, 1.0 - days_since / rw) if rw else 0.0
    conf = 100.0 * (c["weight_touch"] * touch + c["weight_fit"] * fit
                    + c["weight_span"] * span + c["weight_recency"] * recency)
    return {"touch": round(touch, 3), "fit": round(fit, 3), "span": round(span, 3),
            "recency": round(recency, 3), "conf": round(conf, 1)}


def screen_clean(symbol_to_rows):
    """Detect hull lines for every symbol x timeframe, keep the liquid ones, label
    each, and rank by confidence (touch-count led). Each result carries the geometry
    the frontend needs to draw it."""
    tfs = [("1d", None), ("1w", to_weekly), ("1m", to_monthly)]
    on_line = CFG.get("on_line_atr", 0.0)
    atr_win = CFG["hull"].get("atr_window", 14)

    rel = CFG.get("reliability", {})
    min_turnover = rel.get("min_turnover_cr", 0.0)
    turnover_lb = rel.get("turnover_lookback", 20)
    vrb, vbb = rel.get("vol_recent_bars", 3), rel.get("vol_base_bars", 20)

    out = []
    for symbol, daily in symbol_to_rows.items():
        # LIQUIDITY GATE — a stock property, applied once for all timeframes.
        turnover = _turnover_cr(daily, turnover_lb)
        if min_turnover and (turnover is None or turnover < min_turnover):
            continue

        for tf, resample in tfs:
            rows = resample(daily) if resample else daily
            atrv = atr(rows, atr_win)
            if not atrv:
                continue
            lines = detect_hull_lines(rows, tf)
            if not lines:
                continue

            vratio = _vol_ratio(rows, vrb, vbb)
            close = rows[-1][4]
            last_date = datetime.strptime(rows[-1][0][:10], "%Y-%m-%d")
            for ln in lines:
                dist_atr = ln["dist_now_atr"]
                setup = _label_side_sign(ln["side"], dist_atr, on_line)
                fit = _fit_atr(ln, atrv)
                vol = round(vratio, 2) if vratio is not None else None

                # CONF inputs: span = calendar days between first and last touch;
                # days_since = calendar days from the last touch to the latest bar.
                tdates = [tp["date"] for tp in ln["touch_points"]]
                span_days = (datetime.strptime(max(tdates), "%Y-%m-%d")
                             - datetime.strptime(min(tdates), "%Y-%m-%d")).days
                days_since = (last_date - datetime.strptime(ln["last_touch_date"], "%Y-%m-%d")).days
                parts = _conf_components(ln["touch_count"], fit, span_days, days_since)

                out.append({
                    "symbol": symbol, "timeframe": tf,
                    "setup": setup, "role": ln["side"], "line_type": ln["line_type"],
                    "touches": ln["touch_count"], "fit_atr": round(fit, 3),
                    "span_days": span_days, "days_since_touch": days_since,
                    "value_now": ln["value_now"], "distance_atr": dist_atr,
                    "close": round(close, 2),
                    "turnover_cr": round(turnover, 2) if turnover is not None else None,
                    "vol_ratio": vol,
                    "slope": ln["slope"], "first_idx": ln["first_anchor_idx"],
                    "last_idx": ln["last_idx"], "touch_points": ln["touch_points"],
                    "last_touch": ln["last_touch_date"],
                    "first_anchor": ln["first_anchor_date"],
                    "conf_parts": {k: parts[k] for k in ("touch", "fit", "span", "recency")},
                    "confidence": parts["conf"], "score": parts["conf"],
                })
    # DEDUP: the hull turns every edge into a candidate and extends each to now, so
    # adjacent lower/upper-hull vertices near the current bar spawn near-identical
    # parallel lines (e.g. BLUESTONE's two support edges). Collapse to ONE line per
    # (symbol, timeframe, side) — the highest-confidence one (tie: more touches).
    best = {}
    for c in out:
        k = (c["symbol"], c["timeframe"], c["role"])
        cur = best.get(k)
        if cur is None or (c["confidence"], c["touches"]) > (cur["confidence"], cur["touches"]):
            best[k] = c
    out = list(best.values())

    out.sort(key=lambda c: c["confidence"], reverse=True)
    return out
