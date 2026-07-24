"""
Angel One client: log in and fetch daily OHLCV candles.

This module holds the shared broker access used across the app:
    login()          -> authenticate and return a connected SmartConnect
    fetch_candles()  -> pull daily candles for a symbol token, in chunks

`bulk_load.py` imports these to load every stock. Running this file directly
is a quick connection smoke test — it logs in and prints RELIANCE's history:

    python angel.py
"""

import os
import time
from datetime import datetime, timedelta

import pyotp
from dotenv import load_dotenv
from SmartApi import SmartConnect
from tabulate import tabulate

from config import EXCHANGE, SYMBOL, SYMBOL_TOKEN, INTERVAL

START_DATE = datetime(2020, 1, 1)          # first date we want
END_DATE = datetime.now()                  # up to today

# Angel One returns at most 2000 daily candles per request, so we fetch in
# chunks of this many days and stitch the results together.
CHUNK_DAYS = 1800


def login():
    """Log in to Angel One and return a connected SmartConnect object."""
    load_dotenv()  # reads the .env file into environment variables

    api_key = os.getenv("ANGEL_API_KEY")
    client_code = os.getenv("ANGEL_CLIENT_CODE")
    mpin = os.getenv("ANGEL_MPIN")
    totp_secret = os.getenv("ANGEL_TOTP_SECRET")

    # Fail early with a clear message if any secret is missing.
    missing = [
        name
        for name, value in {
            "ANGEL_API_KEY": api_key,
            "ANGEL_CLIENT_CODE": client_code,
            "ANGEL_MPIN": mpin,
            "ANGEL_TOTP_SECRET": totp_secret,
        }.items()
        if not value
    ]
    if missing:
        raise SystemExit(
            "Missing values in .env: " + ", ".join(missing) +
            "\nCopy .env.example to .env and fill these in."
        )

    smart = SmartConnect(api_key=api_key)

    # Turn the TOTP secret into the current 6-digit 2FA code.
    current_otp = pyotp.TOTP(totp_secret).now()

    session = smart.generateSession(client_code, mpin, current_otp)
    if not session.get("status"):
        raise SystemExit("Login failed: " + str(session.get("message")))

    print("Logged in to Angel One.")
    return smart


def fetch_candles(smart, start_date=None, end_date=None,
                  symbol_token=None, exchange=None, verbose=True):
    """
    Fetch daily candles between start_date and end_date, in chunks.

    Defaults reproduce the Slice 1 behaviour (RELIANCE, Jan 2020 -> today) when
    nothing is passed. Slice 3's updater passes a recent start_date; Slice 6's
    bulk loader passes a different symbol_token per stock.
    """
    if start_date is None:
        start_date = START_DATE
    if end_date is None:
        end_date = datetime.now()
    if symbol_token is None:
        symbol_token = SYMBOL_TOKEN
    if exchange is None:
        exchange = EXCHANGE

    all_rows = []
    chunk_start = start_date

    while chunk_start <= end_date:
        chunk_end = min(chunk_start + timedelta(days=CHUNK_DAYS), end_date)

        params = {
            "exchange": exchange,
            "symboltoken": symbol_token,
            "interval": INTERVAL,
            # Angel One expects "YYYY-MM-DD HH:MM" with market hours.
            "fromdate": chunk_start.strftime("%Y-%m-%d") + " 09:15",
            "todate": chunk_end.strftime("%Y-%m-%d") + " 15:30",
        }

        if verbose:
            print(f"Fetching {params['fromdate']} to {params['todate']} ...")
        resp = smart.getCandleData(params)

        if not resp.get("status"):
            raise SystemExit("Data request failed: " + str(resp.get("message")))

        rows = resp.get("data") or []
        all_rows.extend(rows)

        # Move to the day after this chunk's end, and be polite to the API.
        chunk_start = chunk_end + timedelta(days=1)
        time.sleep(0.4)  # stay under Angel One's rate limit

    return all_rows


def main():
    smart = login()
    rows = fetch_candles(smart)

    if not rows:
        print("No data returned.")
        return

    # Each row is [timestamp, open, high, low, close, volume].
    headers = ["Date", "Open", "High", "Low", "Close", "Volume"]
    # Show just the date part of the timestamp for readability.
    display = [[r[0][:10], r[1], r[2], r[3], r[4], r[5]] for r in rows]

    print(tabulate(display, headers=headers, tablefmt="simple"))
    print(f"\nTotal candles: {len(rows)}")
    print(f"Range: {display[0][0]} to {display[-1][0]}")


if __name__ == "__main__":
    main()
