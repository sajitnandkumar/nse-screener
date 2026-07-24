"""
The Nifty 50 constituents, as plain NSE ticker symbols (no "-EQ" suffix).

Angel One needs a numeric token for each; we look those up in instruments.py
from Angel One's official instrument master, so we only maintain names here.

If the index composition changes, edit this list. If any name can't be matched
to a token, bulk_load.py will report it so we can fix the spelling.
"""

NIFTY_50 = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY",
    "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK",
    "LT", "BAJFINANCE", "HCLTECH", "AXISBANK", "ASIANPAINT",
    "MARUTI", "SUNPHARMA", "TITAN", "NESTLEIND", "ULTRACEMCO",
    "WIPRO", "ONGC", "NTPC", "POWERGRID", "M&M",
    "TATAMOTORS", "TATASTEEL", "JSWSTEEL", "ADANIENT", "ADANIPORTS",
    "COALINDIA", "BAJAJFINSV", "HDFCLIFE", "SBILIFE", "GRASIM",
    "BRITANNIA", "DRREDDY", "CIPLA", "EICHERMOT", "HEROMOTOCO",
    "BAJAJ-AUTO", "INDUSINDBK", "APOLLOHOSP", "TATACONSUM", "BPCL",
    "HINDALCO", "TECHM", "LTIM", "SHRIRAMFIN", "DIVISLAB",
]
