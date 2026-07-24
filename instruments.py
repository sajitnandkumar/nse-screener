"""
Look up Angel One's numeric "symbol token" for a stock ticker.

Angel One publishes a big JSON file listing every tradable instrument (stocks,
futures, options...) with its token. We download it once, cache it on disk, and
use it to translate ticker names ("RELIANCE") into the tokens the data API
needs ("2885").

The cache file (instruments.json) is git-ignored because it's large and
regenerable. Delete it to force a fresh download (e.g. after new listings).
"""

import json
import os
import urllib.request

# Angel One's public instrument master (no login needed to download it).
SCRIP_MASTER_URL = (
    "https://margincalculator.angelbroking.com/OpenAPI_File/files/"
    "OpenAPIScripMaster.json"
)
CACHE_FILE = "instruments.json"


def _download_master():
    """Download the instrument master JSON and cache it to disk."""
    print("Downloading Angel One instrument master (one-time, ~a few MB) ...")
    with urllib.request.urlopen(SCRIP_MASTER_URL, timeout=60) as resp:
        data = resp.read()
    with open(CACHE_FILE, "wb") as f:
        f.write(data)
    return json.loads(data)


def _load_master():
    """Load the instrument master from cache, downloading it if missing."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "rb") as f:
            return json.load(f)
    return _download_master()


def build_nse_equity_map():
    """
    Return a dict mapping NSE equity ticker -> token.

    We keep only cash-market equities: exchange segment "NSE" and a trading
    symbol ending in "-EQ" (e.g. "RELIANCE-EQ"). The key is the bare ticker
    ("RELIANCE") so it matches the names in nifty50.py.
    """
    master = _load_master()
    mapping = {}
    for row in master:
        if row.get("exch_seg") == "NSE" and row.get("symbol", "").endswith("-EQ"):
            ticker = row["symbol"][:-3]  # strip the "-EQ"
            mapping[ticker] = row["token"]
    return mapping


def resolve_tokens(tickers):
    """
    Given a list of tickers, return (resolved, missing) where:
      resolved = list of (ticker, symbol_with_EQ, token)
      missing  = tickers we couldn't find (likely a name mismatch)
    """
    mapping = build_nse_equity_map()
    resolved, missing = [], []
    for ticker in tickers:
        token = mapping.get(ticker)
        if token:
            resolved.append((ticker, ticker + "-EQ", token))
        else:
            missing.append(ticker)
    return resolved, missing
