"""
Detect diagonal support/resistance TRENDLINES from candle data.

A trendline is a sloped line touching a series of swing lows (a rising/falling
support trendline) or swing highs (a resistance trendline). This is what the
horizontal-level detector cannot see: e.g. a stock that has ridden up along a
line of higher-lows for years and just pulled back to touch it again.

Method (per timeframe):
1. Find swing lows and swing highs (local minima / maxima), keeping their bar
   INDEX so we can compute a slope.
2. For a support trendline: try every pair of swing lows as anchors, form the
   straight line through them, and count how many OTHER swing lows touch that
   line (within a tolerance). Keep the line only if it's a genuine floor —
   almost no swing low sits meaningfully BELOW it — and it has >= MIN_TOUCHES.
3. Mirror the whole thing for resistance trendlines using swing highs (a
   genuine ceiling — almost nothing above it).
4. Deduplicate near-identical lines and return the strongest few.

Pure Python. On daily data there can be many swing points, so we use a wider
pivot window on lower timeframes (fewer, more significant swings) to keep the
pair search fast.
"""

import numpy as np

from settings import CFG


def _close_swings(closes, window):
    """Swing lows/highs measured on CLOSING price. Returns (low_idx, high_idx)."""
    lows, highs = [], []
    n = len(closes)
    for i in range(window, n - window):
        seg = closes[i - window:i + window + 1]
        c = closes[i]
        if c == min(seg):
            lows.append(i)
        if c == max(seg):
            highs.append(i)
    return lows, highs


def _fit_clean(closes_np, dates, atrv, pivots, role, pivot_min_span, strict=True):
    """
    Fit lines through pairs of close-pivots and keep only CLEAN ones:
    tight touches (fit_atr), few wrong-side closes (violations), enough touches,
    long enough span. All tolerances are in ATR. Returns line dicts.
    """
    tol = CFG["touch_tol_atr"] * atrv
    buf = CFG["buffer_atr"] * atrv
    last = len(closes_np) - 1
    lines = []

    for a in range(len(pivots)):
        for b in range(a + 1, len(pivots)):
            ia, ib = pivots[a], pivots[b]
            if ib - ia < pivot_min_span:
                continue
            slope = (closes_np[ib] - closes_np[ia]) / (ib - ia)

            # Touches: pivots whose close is within tol of the line.
            piv_idx = np.array(pivots)
            piv_line = closes_np[ia] + slope * (piv_idx - ia)
            piv_dist = np.abs(closes_np[piv_idx] - piv_line)
            touch_mask = piv_dist <= tol
            touch_idx = piv_idx[touch_mask]
            if len(touch_idx) < (CFG["min_touches"] if strict else 2):
                continue

            first = int(touch_idx.min())
            if last - first < pivot_min_span:
                continue

            # fit_atr: average touch distance to the line, in ATR (tightness).
            fit_atr = float(piv_dist[touch_mask].mean() / atrv)
            if strict and fit_atr > CFG["max_fit_atr"]:
                continue

            # Violations: bars in the active span that CLOSE on the wrong side.
            xs = np.arange(first, last + 1)
            line_vals = closes_np[ia] + slope * (xs - ia)
            seg = closes_np[first:last + 1]
            if role == "support":
                violations = int(np.sum(seg < line_vals - buf))
                wrongside_atr = float(max(0.0, (line_vals - seg).max())) / atrv
            else:
                violations = int(np.sum(seg > line_vals + buf))
                wrongside_atr = float(max(0.0, (seg - line_vals).max())) / atrv
            if strict and violations > CFG["max_violations"]:
                continue
            # Envelope: reject if price ever closed too far past the line on the
            # wrong side (a decisively broken line). Trend-safe — the "right"
            # side (e.g. price above a support) is never penalised.
            if strict and wrongside_atr > CFG["max_wrongside_atr"]:
                continue

            value_now = float(closes_np[ia] + slope * (last - ia))
            lines.append({
                "role": role,
                "slope": slope,
                "touches": int(len(touch_idx)),
                "fit_atr": round(fit_atr, 3),
                "violations": violations,
                "span": int(last - first),
                "first_idx": first,
                "last_idx": last,
                "value_now": round(value_now, 2),
                "touch_points": [{"idx": int(i), "date": dates[i], "price": float(closes_np[i])}
                                 for i in touch_idx],
                "last_touch": dates[int(touch_idx.max())],
            })
    return lines


def _dedupe_clean(lines, atrv):
    """Keep the single best (lowest fit, then most touches) line per cluster."""
    best = {}
    for ln in lines:
        val_bin = round(ln["value_now"] / max(atrv, 0.01))
        slope_bin = round(ln["slope"] / max(atrv * 0.05, 1e-6))
        key = (ln["role"], slope_bin, val_bin)
        cur = best.get(key)
        if cur is None or (ln["fit_atr"], -ln["touches"]) < (cur["fit_atr"], -cur["touches"]):
            best[key] = ln
    return list(best.values())


def detect_clean_lines(rows, atrv, pivot_window, min_span_bars, strict=True):
    """
    Close-based, unified line detection (support from swing-low closes,
    resistance from swing-high closes). Horizontal is just slope ~ 0.
    Returns cleaned + deduped lines, tagged line_type. strict=False keeps lines
    that fail the fit/violation filters (for diagnostics / contact-sheet display).
    """
    if atrv is None or len(rows) < pivot_window * 2 + min_span_bars + 2:
        return []
    closes = [r[4] for r in rows]
    dates = [r[0][:10] for r in rows]
    closes_np = np.array(closes, dtype=float)

    lows, highs = _close_swings(closes, pivot_window)
    lines = (_fit_clean(closes_np, dates, atrv, lows, "support", min_span_bars, strict) +
             _fit_clean(closes_np, dates, atrv, highs, "resistance", min_span_bars, strict))
    lines = _dedupe_clean(lines, atrv)

    # Horizontal iff the line barely moves over its whole span (in ATR terms).
    for ln in lines:
        total_move_atr = abs(ln["slope"] * ln["span"]) / atrv
        ln["line_type"] = "horizontal" if total_move_atr < CFG["horizontal_total_atr"] else "trendline"

    # Horizontals must hug tighter than trendlines to be worth showing.
    if strict:
        mfh = CFG.get("max_fit_atr_horizontal", 1e9)
        lines = [l for l in lines if not (l["line_type"] == "horizontal" and l["fit_atr"] > mfh)]
    return lines
