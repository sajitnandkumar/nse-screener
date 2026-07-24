"""
The screening engine (close-based, cleanliness-filtered).

For each symbol x timeframe it detects clean support/resistance lines
(trendlines.detect_clean_lines, all on CLOSING prices), keeps only those price
is currently near (ATR proximity gate), labels each by side + where price sits,
and scores them fit-first so the tightest lines rank highest.

Four setups (side of the line + which side price is on now):
  - Support Reversal    : price at / above a support line   (may bounce)
  - Support Breakdown   : price has closed below a support line
  - Resistance Reversal : price at / below a resistance line (may reject)
  - Resistance Breakout : price has closed above a resistance line

"At the line" (within on_line_atr) counts as a Reversal, not a break — a hair
past the line is a test, not a decisive break.
"""

import json
import os

from atr import atr
from resample import to_weekly, to_monthly
from trendlines import detect_clean_lines
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
    """
    Label from (line side) + (sign of signed_dist), in ATR. Positive = price
    above the line. Within `on_line` ATR of the line -> treated as a Reversal
    (price is sitting on the line, not decisively past it).
    """
    if abs(signed_dist) <= on_line:
        return "Support Reversal" if role == "support" else "Resistance Reversal"
    above = signed_dist >= 0
    if role == "support":
        return "Support Reversal" if above else "Support Breakdown"
    return "Resistance Breakout" if above else "Resistance Reversal"


def _confidence(ln):
    """
    Confidence score 0-100: how EXACTLY the closes sit on the line (tightness)
    plus how MANY times it was touched. Tightness dominates, so lines whose
    touches sit right on the line rank highest; loosely-touched lines (like
    EIDPARRY, fit 0.17) score low.
    """
    c = CFG["confidence"]
    tightness = max(0.0, 1.0 - ln["fit_atr"] / c["fit_ref_atr"])   # 1.0 = exact
    count = min(1.0, ln["touches"] / c["target_touches"])
    wt = c["weight_tight"]
    return round(100.0 * (wt * tightness + (1 - wt) * count), 1)


def screen_clean(symbol_to_rows):
    """
    Returns ONLY setups where a clean line exists AND price is within
    proximity_tol_atr of it now, ranked best-first. Most stocks produce nothing.
    Each result carries the geometry needed to draw it.
    """
    tfs = [("1d", None), ("1w", to_weekly), ("1m", to_monthly)]
    prox = CFG["proximity_tol_atr"]
    on_line = CFG.get("on_line_atr", 0.0)
    out = []

    for symbol, daily in symbol_to_rows.items():
        for tf, resample in tfs:
            rows = resample(daily) if resample else daily
            atrv = atr(rows)
            if not atrv:
                continue
            p = CFG["timeframes"][tf]
            lines = detect_clean_lines(rows, atrv, p["pivot_window"], p["min_span_bars"])
            if not lines:
                continue

            close = rows[-1][4]
            for ln in lines:
                dist_atr = (close - ln["value_now"]) / atrv
                if abs(dist_atr) > prox:          # proximity GATE (not a label)
                    continue
                conf = _confidence(ln)
                if conf < CFG["min_confidence"]:  # only confident setups
                    continue
                setup = _label_side_sign(ln["role"], dist_atr, on_line)
                out.append({
                    "symbol": symbol, "timeframe": tf,
                    "setup": setup, "role": ln["role"], "line_type": ln["line_type"],
                    "touches": ln["touches"], "fit_atr": ln["fit_atr"],
                    "violations": ln["violations"], "span": ln["span"],
                    "value_now": ln["value_now"], "distance_atr": round(dist_atr, 2),
                    "slope": ln["slope"], "first_idx": ln["first_idx"],
                    "last_idx": ln["last_idx"], "touch_points": ln["touch_points"],
                    "last_touch": ln["last_touch"],
                    "confidence": conf, "score": conf,
                })
    out.sort(key=lambda c: c["confidence"], reverse=True)
    return out
