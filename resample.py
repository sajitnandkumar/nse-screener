"""
Turn daily candles into weekly and monthly candles.

We only download daily data, but the screener needs to look at 1-week and
1-month timeframes too. Rather than fetch them separately, we "resample":
group daily bars into weeks/months and combine each group into one candle:

    open   = first day's open
    high   = highest high in the group
    low    = lowest low in the group
    close  = last day's close
    volume = sum of the group's volume

That is exactly how a weekly/monthly candle is defined.
"""

from datetime import datetime


def _aggregate(rows, key_func):
    """Group `rows` (oldest first) by key_func(date) and build one candle per group."""
    groups = {}
    order = []
    for r in rows:
        k = key_func(r[0])
        if k not in groups:
            groups[k] = []
            order.append(k)
        groups[k].append(r)

    out = []
    for k in order:
        g = groups[k]
        out.append((
            g[-1][0],                 # date: last day in the group
            g[0][1],                  # open: first day's open
            max(x[2] for x in g),     # high
            min(x[3] for x in g),     # low
            g[-1][4],                 # close: last day's close
            sum(x[5] for x in g),     # volume
        ))
    return out


def to_weekly(rows):
    """Group daily rows into ISO calendar weeks."""
    def key(date_str):
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        iso = dt.isocalendar()        # (iso_year, iso_week, iso_weekday)
        return (iso[0], iso[1])
    return _aggregate(rows, key)


def to_monthly(rows):
    """Group daily rows into calendar months ('YYYY-MM')."""
    return _aggregate(rows, lambda date_str: date_str[:7])
