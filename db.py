"""
Local storage for candle data, using SQLite.

SQLite is just a single file on disk (nse_data.db) — no database server to
install or run. Perfect for a local app. Python has it built in.

One table, `candles`, holds daily OHLCV rows for any symbol. The primary key is
(symbol, date), so saving the same day twice UPDATES the row instead of adding a
duplicate. That "upsert" behaviour is what will make daily updates painless
later — we can re-fetch overlapping dates safely.
"""

import sqlite3

DB_FILE = "nse_data.db"


def connect():
    """Open a connection to the database file (creates it if missing)."""
    return sqlite3.connect(DB_FILE)


def init_db():
    """Create the candles table if it doesn't already exist."""
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS candles (
                symbol  TEXT NOT NULL,
                date    TEXT NOT NULL,   -- 'YYYY-MM-DD'
                open    REAL,
                high    REAL,
                low     REAL,
                close   REAL,
                volume  INTEGER,
                PRIMARY KEY (symbol, date)
            )
            """
        )


def save_candles(symbol, rows):
    """
    Save candle rows for one symbol.

    `rows` are Angel One's raw candles: [timestamp, open, high, low, close, vol].
    We keep just the date part of the timestamp. INSERT OR REPLACE performs the
    upsert on the (symbol, date) primary key.

    Returns the number of rows written.
    """
    records = [
        (symbol, r[0][:10], r[1], r[2], r[3], r[4], r[5])
        for r in rows
    ]
    with connect() as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO candles
                (symbol, date, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            records,
        )
    return len(records)


def list_symbols():
    """Return every symbol that has data stored, alphabetically."""
    with connect() as conn:
        cursor = conn.execute(
            "SELECT DISTINCT symbol FROM candles ORDER BY symbol"
        )
        return [row[0] for row in cursor.fetchall()]


def last_stored_date(symbol):
    """
    Return the newest date we already have for a symbol, as 'YYYY-MM-DD',
    or None if we have nothing stored yet. Used to fetch only new days.
    """
    with connect() as conn:
        cursor = conn.execute(
            "SELECT MAX(date) FROM candles WHERE symbol = ?",
            (symbol,),
        )
        return cursor.fetchone()[0]  # None if no rows exist


def read_candles(symbol):
    """Return all stored rows for a symbol, oldest first."""
    with connect() as conn:
        cursor = conn.execute(
            """
            SELECT date, open, high, low, close, volume
            FROM candles
            WHERE symbol = ?
            ORDER BY date ASC
            """,
            (symbol,),
        )
        return cursor.fetchall()
