"""
Extra tickers to load beyond the Nifty 50 — your personal watchlist.

Add any NSE ticker here (bare symbol, no "-EQ") and re-run bulk_load.py to
fetch and store it. Names that can't be resolved to a token are reported and
skipped, same as the Nifty 50.
"""

WATCHLIST = [
    "EIDPARRY",   # E.I.D. Parry — the ascending-trendline example
]
