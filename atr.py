"""
Average True Range (ATR) — a standard measure of how much a stock typically
moves in one bar. We use it to express "distance to the level" in a way that is
comparable across stocks: 0.5 ATR from a level means the same thing for a
cheap volatile stock and an expensive calm one, whereas "0.5%" does not.

True Range for a bar = the largest of:
    high - low
    |high - previous close|
    |low  - previous close|

ATR = the average True Range over the last `period` bars (default 14).
"""


def atr(rows, period=14):
    """
    Return the latest ATR value (in price units) for `rows`
    (date, open, high, low, close, volume), oldest first. Returns None if there
    aren't enough bars.
    """
    if len(rows) < period + 1:
        return None

    true_ranges = []
    for i in range(1, len(rows)):
        high, low, prev_close = rows[i][2], rows[i][3], rows[i - 1][4]
        true_ranges.append(max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close),
        ))

    # Simple average of the most recent `period` true ranges.
    recent = true_ranges[-period:]
    return sum(recent) / len(recent)
