"""
Moving-average crossovers — price CLOSING across an SMA / EMA on Daily / Weekly /
Monthly bars.

A "Bullish" crossover = the close moved from below the average to above it on the
latest bar(s); "Bearish" = from above to below. One event per (symbol, timeframe,
MA type, period) when the cross happened within `fresh_bars` of the newest bar.

Averages are computed on closes only. EMA is seeded with the SMA of the first
`period` closes and then smoothed with k = 2 / (period + 1) — the frontend draws
the line with the SAME formula (app.js maSeries), so what you see is what fired.
Knobs live in config.yaml under `crossovers:`.
"""

from datetime import datetime, timedelta

from breakouts import _rvol
from resample import to_weekly, to_monthly
from settings import CFG

XC = CFG["crossovers"]
TFS = ("1d", "1w", "1m")


def sma(closes, n):
    """Simple moving average; None until `n` closes exist."""
    out, s = [None] * len(closes), 0.0
    for i, c in enumerate(closes):
        s += c
        if i >= n:
            s -= closes[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def ema(closes, n):
    """Exponential moving average, SMA-seeded; None until `n` closes exist."""
    out = [None] * len(closes)
    if len(closes) < n:
        return out
    k = 2.0 / (n + 1)
    e = sum(closes[:n]) / n
    out[n - 1] = e
    for i in range(n, len(closes)):
        e = (closes[i] - e) * k + e
        out[i] = e
    return out


MA = {"SMA": sma, "EMA": ema}


def _forming(tf, last_date):
    """Is the newest weekly/monthly bar still being built? (Daily bars are complete.)"""
    d = datetime.strptime(last_date[:10], "%Y-%m-%d")
    if tf == "1w":
        return d.weekday() < 4
    if tf == "1m":
        nxt = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
        return (nxt - d).days > 4
    return False


def scan_symbol(symbol, daily, turnover=None):
    out = []
    for tf in TFS:
        rows = daily if tf == "1d" else (to_weekly(daily) if tf == "1w" else to_monthly(daily))
        closes = [r[4] for r in rows]
        vols = [r[5] or 0 for r in rows]
        n = len(rows)
        fresh = XC["fresh_bars"][tf]
        forming_last = _forming(tf, rows[-1][0])
        for ma_type, fn in MA.items():
            for period in XC["periods"]:
                if n < period + 2:
                    continue                       # not enough history for this average
                m = fn(closes, period)
                for t in range(max(period, n - fresh), n):
                    if m[t] is None or m[t - 1] is None:
                        continue
                    above_now, above_prev = closes[t] > m[t], closes[t - 1] > m[t - 1]
                    if above_now == above_prev:
                        continue
                    rv = _rvol(vols, t, XC["rvol_bars"][tf])
                    out.append({
                        "symbol": symbol, "timeframe": tf,
                        "ma_type": ma_type, "period": period,
                        "direction": "Bullish" if above_now else "Bearish",
                        "cross_date": rows[t][0][:10], "bars_ago": n - 1 - t,
                        "forming": bool(t == n - 1 and forming_last),
                        "close": round(closes[-1], 2), "ma_value": round(m[-1], 2),
                        "dist_pct": round((closes[-1] - m[-1]) / m[-1] * 100, 2),
                        "cross_close": round(closes[t], 2), "cross_ma": round(m[t], 2),
                        "rvol": round(rv, 2) if rv is not None else None,
                        "turnover_cr": round(turnover, 2) if turnover is not None else None,
                    })
    return out


def scan_all(symbol_to_rows):
    """Every liquid symbol; newest crosses first, then volume surge."""
    from screener import _turnover_cr
    rel = CFG.get("reliability", {})
    min_t, lb = rel.get("min_turnover_cr", 0.0), rel.get("turnover_lookback", 20)
    out = []
    for symbol, daily in symbol_to_rows.items():
        turnover = _turnover_cr(daily, lb)
        if min_t and (turnover is None or turnover < min_t):
            continue
        out.extend(scan_symbol(symbol, daily, turnover))
    out.sort(key=lambda e: (e["bars_ago"], -(e["rvol"] or 0)))
    return out


if __name__ == "__main__":
    import db
    from collections import Counter
    res = scan_all({s: db.read_candles(s) for s in db.list_symbols()})
    print(len(res), "crossovers")
    for k, v in sorted(Counter((e["timeframe"], e["ma_type"], e["period"], e["direction"]) for e in res).items()):
        print(" ", *k, v)
