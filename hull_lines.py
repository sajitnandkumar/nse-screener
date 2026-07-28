"""
Hull-based trendline detector (exact definition — CLAUDE.md Slice 22).

A line is anchored on CLOSING prices. Rule 2 says: between a line's two anchors,
NO close may be on the wrong side of it (no close below a support, none above a
resistance). That constraint IS the convex hull of the close series:

  - every LOWER-hull edge is a valid SUPPORT   line — by construction nothing
    closes below it between its anchors. Zero violations, no filtering.
  - every UPPER-hull edge is a valid RESISTANCE line — nothing closes above it.

No regression, no fit-and-filter (a least-squares line would break rule 2). We
compute the hull on a trailing per-timeframe WINDOW so a clean recent line isn't
hidden beneath older extremes; rule 2 still holds exactly inside the window. Each
edge is extended to the last bar, touches are counted, and a line is kept only if
it is tested enough (min_touches) and live (a touch within recency_days).
"""

from datetime import datetime

from atr import atr
from settings import CFG


def _cross(o, a, b):
    """Cross product of OA x OB. >0 = left/CCW turn, <0 = right/CW turn, 0 = collinear."""
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _lower_hull(pts):
    """Indices of the lower convex hull of pts=[(x,y)...] with x strictly increasing.
    Collinear middle points are dropped as vertices (they still fall exactly on the
    edge, so they get counted later as touches)."""
    hull = []
    for i in range(len(pts)):
        while len(hull) >= 2 and _cross(pts[hull[-2]], pts[hull[-1]], pts[i]) <= 0:
            hull.pop()
        hull.append(i)
    return hull


def _upper_hull(pts):
    """Indices of the upper convex hull (mirror of the lower hull)."""
    hull = []
    for i in range(len(pts)):
        while len(hull) >= 2 and _cross(pts[hull[-2]], pts[hull[-1]], pts[i]) >= 0:
            hull.pop()
        hull.append(i)
    return hull


def _make_line(closes, dates, a, b, side, start, atrv, tol, cfg, timeframe):
    """Turn one hull edge (local anchor indices a<b) into a line dict, or None if it
    fails min_touches / recency. Indices in the output are ABSOLUTE (into full rows)."""
    last = len(closes) - 1
    slope = (closes[b] - closes[a]) / (b - a)

    def line_at(i):
        return closes[a] + slope * (i - a)

    # Touches: bars from the first anchor to now whose close sits on the line.
    # (The anchors are on the line by construction; collinear bars land here too.)
    touch = [i for i in range(a, last + 1) if abs(closes[i] - line_at(i)) <= tol]
    if len(touch) < cfg["min_touches"]:
        return None

    # Recency: the most recent touch must be within recency_days calendar days.
    last_touch = max(touch)
    days = (datetime.strptime(dates[last], "%Y-%m-%d")
            - datetime.strptime(dates[last_touch], "%Y-%m-%d")).days
    if days > cfg["recency_days"]:
        return None

    value_now = line_at(last)
    dist_now_atr = (closes[last] - value_now) / atrv
    # Horizontal vs trend = how much the line's price changes over what's DRAWN
    # (first anchor -> now), in ATR. This is span-correct: a short steep line has a
    # real total move (trend), and a long gently-sloping line accumulates a real
    # total move too (trend); only a genuinely flat line stays "horizontal". Neither
    # total-move-between-anchors nor slope-per-bar alone gets both right.
    total_move_atr = abs(slope) * (last - a) / atrv
    # Reject trend-envelope lines: a line that travels this many ATR over its drawn
    # extent is the ceiling/floor of a runaway move (e.g. the upper hull of a 65x
    # uptrend), not a tradeable S/R level.
    if total_move_atr > cfg.get("max_travel_atr", 1e9):
        return None
    line_type = ("horizontal" if total_move_atr < cfg.get("horizontal_total_atr", 0.5)
                 else "trendline")

    return {
        "timeframe": timeframe, "side": side, "line_type": line_type,
        "slope": slope, "touch_count": len(touch),
        "first_anchor_date": dates[a], "last_touch_date": dates[last_touch],
        "value_now": round(value_now, 2), "dist_now_atr": round(dist_now_atr, 2),
        # geometry for drawing (absolute indices into the full row list)
        "first_anchor_idx": start + a, "last_idx": start + last,
        "anchor_points": [{"idx": start + a, "date": dates[a], "price": round(closes[a], 2)},
                          {"idx": start + b, "date": dates[b], "price": round(closes[b], 2)}],
        "touch_points": [{"idx": start + i, "date": dates[i], "price": round(closes[i], 2)}
                         for i in touch],
    }


def detect_hull_lines(rows, timeframe):
    """Return the hull-based support/resistance lines for one symbol's candles on one
    timeframe. `rows` = (date, open, high, low, close, volume), oldest first."""
    cfg = CFG["hull"]
    atrv = atr(rows, cfg.get("atr_window", 14))
    if not atrv or len(rows) < cfg["min_touches"] + 1:
        return []

    # Trailing window (None = full history) — where rule 2 is guaranteed.
    lb = cfg.get("lookback", {}).get(timeframe)
    start = max(0, len(rows) - lb) if lb else 0
    win = rows[start:]
    closes = [r[4] for r in win]
    dates = [r[0][:10] for r in win]
    pts = [(i, closes[i]) for i in range(len(closes))]
    tol = cfg["touch_tol_atr"] * atrv

    lines = []
    for side, hull in (("support", _lower_hull(pts)), ("resistance", _upper_hull(pts))):
        for k in range(len(hull) - 1):
            ln = _make_line(closes, dates, hull[k], hull[k + 1], side,
                            start, atrv, tol, cfg, timeframe)
            if ln:
                lines.append(ln)
    return lines
