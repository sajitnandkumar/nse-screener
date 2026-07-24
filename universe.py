"""
The stock universe, read from NSE's official equity master (EQUITY_L.csv).

Download it from NSE ("Securities available for trading" / EQUITY_L.csv) and
drop it in this folder. It lists every NSE-listed equity (SYMBOL, NAME, SERIES,
...) and — unlike Angel One's instrument dump — contains NO ETFs, so it's a
clean stock-only universe.

We take every SYMBOL in the file. bulk_load.py then resolves each to an Angel
One token (any that don't resolve are reported and skipped).
"""

import csv
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(_HERE, "EQUITY_L.csv")


def load_universe():
    """Return every ticker in EQUITY_L.csv (order preserved, de-duplicated).
    Returns [] if the file isn't present so callers can fall back."""
    if not os.path.exists(CSV_FILE):
        return []
    tickers = []
    with open(CSV_FILE, newline="") as f:
        reader = csv.reader(f)
        next(reader, None)                      # skip header row
        for row in reader:
            if row and row[0].strip():
                tickers.append(row[0].strip())
    return list(dict.fromkeys(tickers))
