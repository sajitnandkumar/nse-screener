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
import time

import requests

# Angel One's public instrument master (no login needed to download it).
SCRIP_MASTER_URL = (
    "https://margincalculator.angelbroking.com/OpenAPI_File/files/"
    "OpenAPIScripMaster.json"
)
CACHE_FILE = "instruments.json"


def _download_master(retries=5):
    """
    Download the instrument master JSON (~35 MB) and cache it. This large file
    sometimes drops mid-download (IncompleteRead), so we retry, and only cache
    it after it fully downloads AND parses as valid JSON.
    """
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            print(f"Downloading Angel One instrument master (attempt {attempt}/{retries}) ...")
            resp = requests.get(SCRIP_MASTER_URL, timeout=180)
            resp.raise_for_status()
            data = resp.content
            master = json.loads(data)          # validate before trusting/caching
            with open(CACHE_FILE, "wb") as f:
                f.write(data)
            return master
        except Exception as exc:               # network drop, incomplete read, bad JSON
            last_err = exc
            print(f"  download failed ({exc}); retrying ...")
            time.sleep(3 * attempt)
    raise RuntimeError(f"Could not download instrument master after {retries} tries: {last_err}")


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
