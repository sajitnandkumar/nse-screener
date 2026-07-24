"""
Slice 6: Load (and keep updated) daily history for a basket of NSE stocks.

Run with:  python bulk_load.py

What it does:
- Resolves each Nifty 50 ticker to its Angel One token (instruments.py).
- Logs in once.
- For each stock, fetches only the days we don't already have (same
  incremental trick as update_reliance.py), then saves them.
- Skips any stock that errors and reports it at the end, so one bad symbol
  never aborts the whole run.

Because it's incremental, this is ALSO your daily update command for the whole
basket — run it once after market close and every stock stays current.
"""

import time
from datetime import datetime

import db
import screener
from angel import START_DATE, login, fetch_candles
from instruments import resolve_tokens
from nifty50 import NIFTY_50
from universe import load_universe
from watchlist import WATCHLIST

SLEEP_BETWEEN_STOCKS = 0.5  # seconds, to stay under Angel One's rate limit


def main():
    db.init_db()

    # Full NSE universe from EQUITY_L.csv if present, else fall back to Nifty 50.
    # Watchlist is always added on top.
    base = load_universe() or NIFTY_50
    tickers = list(dict.fromkeys(base + WATCHLIST))
    print(f"Universe: {len(tickers)} tickers "
          f"({'EQUITY_L.csv' if load_universe() else 'Nifty 50 fallback'}).")
    resolved, missing = resolve_tokens(tickers)
    print(f"Resolved {len(resolved)}/{len(tickers)} tickers to tokens.")
    if missing:
        preview = ", ".join(missing[:15]) + (" ..." if len(missing) > 15 else "")
        print(f"Could not resolve {len(missing)} (skipped): {preview}")

    smart = login()

    loaded, failed = [], []
    total = len(resolved)

    for i, (ticker, symbol, token) in enumerate(resolved, 1):
        # Incremental: only fetch days newer than what we already stored.
        last_date = db.last_stored_date(symbol)
        start = datetime.strptime(last_date, "%Y-%m-%d") if last_date else START_DATE

        try:
            rows = fetch_candles(
                smart,
                start_date=start,
                symbol_token=token,
                verbose=False,
            )
            before = len(db.read_candles(symbol))
            db.save_candles(symbol, rows)
            after = len(db.read_candles(symbol))
            added = after - before
            print(f"[{i:>2}/{total}] {symbol:<14} +{added:<4} new  (total {after})")
            loaded.append(symbol)
        except Exception as exc:  # keep going even if one stock fails
            print(f"[{i:>2}/{total}] {symbol:<14} FAILED: {exc}")
            failed.append(symbol)

        time.sleep(SLEEP_BETWEEN_STOCKS)

    print(f"\nDone. Loaded {len(loaded)} stock(s). Failed: {len(failed)}.")
    if failed:
        preview = ", ".join(failed[:15]) + (" ..." if len(failed) > 15 else "")
        print(f"  (re-run bulk_load.py to retry failures — it's incremental: {preview})")

    # Build the screen cache so the web app opens instantly.
    print("\nBuilding screen cache (screening every stock; takes a few minutes) ...")
    n = screener.build_cache()
    print(f"Screen cache built: {n} setups written to screen_cache.json")
    print("\nNow run:  ./venv/bin/uvicorn app:app --reload   (open http://127.0.0.1:8000)")


if __name__ == "__main__":
    main()
