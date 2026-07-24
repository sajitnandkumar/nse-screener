"""
Local web server exposing the CLEAN close-based screener over HTTP.

Run with:  ./venv/bin/uvicorn app:app --reload

  GET /api/screener?tf=1d
      -> ranked shortlist of clean setups for that timeframe
  GET /api/ohlcv?symbol=RELIANCE-EQ&tf=1d&focus=trendline
      -> that stock's candles plus the clean line(s) to draw

Screening uses screener.screen_clean / trendlines.detect_clean_lines (all on
CLOSING prices, ATR-normalised, filtered for cleanliness). The JSON shape is
kept identical to the previous version so the frontend is unchanged apart from
an added FIT column.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

import db
import screener
from atr import atr
from resample import to_weekly, to_monthly

app = FastAPI(title="NSE S/R Screener")

_RESAMPLE = {"1d": None, "1w": to_weekly, "1m": to_monthly}

# The full screen is the same for every request in a session (data is static),
# and scanning all stocks x timeframes takes a few seconds, so cache it.
_screen_cache = None


def _all_candidates():
    global _screen_cache
    if _screen_cache is None:
        # Prefer the on-disk cache built by bulk_load (instant); only compute
        # live if it's missing (e.g. first run before any cache was built).
        cached = screener.load_cache()
        if cached is not None:
            _screen_cache = cached
        else:
            symbols = db.list_symbols()
            _screen_cache = screener.screen_clean({s: db.read_candles(s) for s in symbols})
    return _screen_cache


def _rows_for(symbol, tf):
    if tf not in _RESAMPLE:
        raise HTTPException(status_code=400, detail=f"Unknown timeframe: {tf}")
    daily = db.read_candles(symbol)
    if not daily:
        raise HTTPException(status_code=404, detail=f"No data for {symbol}")
    rs = _RESAMPLE[tf]
    return rs(daily) if rs else daily


_STATE_TEXT = {
    "Support Reversal": "price holding above the support line",
    "Support Breakdown": "price has closed below the support line",
    "Resistance Reversal": "price holding below the resistance line",
    "Resistance Breakout": "price has closed above the resistance line",
}


@app.get("/api/screener")
def get_screener(tf: str = Query("1d")):
    """Ranked clean shortlist for one timeframe (already sorted by score)."""
    if tf not in _RESAMPLE:
        raise HTTPException(status_code=400, detail=f"Unknown timeframe: {tf}")
    rows = [{
        "symbol": c["symbol"], "setup": c["setup"], "role": c["role"],
        "line_type": c["line_type"], "touches": c["touches"],
        "fit_atr": c["fit_atr"], "confidence": c["confidence"],
        "distance_atr": c["distance_atr"],
        "timeframe": c["timeframe"], "score": c["score"],
    } for c in _all_candidates() if c["timeframe"] == tf]
    return {"timeframe": tf, "count": len(rows), "rows": rows}


@app.get("/api/ohlcv")
def get_ohlcv(symbol: str = Query(...), tf: str = Query("1d"),
              focus: str = Query(None)):
    """Candles plus the clean line(s); `focus` picks which is emphasised."""
    rows = _rows_for(symbol, tf)
    atrv = atr(rows)
    dates = [r[0][:10] for r in rows]
    candles = [{"time": r[0][:10], "open": r[1], "high": r[2],
                "low": r[3], "close": r[4], "volume": r[5]} for r in rows]
    current = rows[-1][4]

    # Flagged setups for this symbol/tf (already gated + labelled + sorted).
    setups = [c for c in _all_candidates()
              if c["symbol"] == symbol and c["timeframe"] == tf]
    if focus not in ("horizontal", "trendline"):
        focus = setups[0]["line_type"] if setups else None
    focused = next((c for c in setups if c["line_type"] == focus), None)
    if focused is None and setups:
        focused = setups[0]

    # Draw ONLY the flagged setup line (drawing every detected line clutters the
    # chart and, worse, blows up the price axis when a projected line runs to an
    # extreme value). No active setup -> no line.
    lines = []
    if focused:
        first, last = focused["first_idx"], focused["last_idx"]
        start_price = round(focused["value_now"] + focused["slope"] * (first - last), 2)
        lines.append({
            "type": focused["line_type"], "role": focused["role"],
            "price": focused["value_now"], "touches": focused["touches"],
            "is_setup": True,
            "start": {"time": dates[first], "price": start_price},
            "end": {"time": dates[last], "price": focused["value_now"]},
            "touch_points": [{"time": tp["date"], "price": tp["price"]}
                             for tp in focused["touch_points"]],
        })

    context = None
    if focused:
        context = {
            "setup": focused["setup"], "role": focused["role"],
            "line_type": focused["line_type"], "touches": focused["touches"],
            "fit_atr": focused["fit_atr"], "confidence": focused["confidence"],
            "state": _STATE_TEXT.get(focused["setup"], ""),
            "distance_atr": focused["distance_atr"],
            "last_touch": focused["last_touch"][:10],
        }

    return {"symbol": symbol, "timeframe": tf, "current": current,
            "candles": candles, "lines": lines, "context": context}


# Serve the frontend last so /api routes take precedence.
app.mount("/", StaticFiles(directory="static", html=True), name="static")
