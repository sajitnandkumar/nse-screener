"""
Build the static site into ./site — a self-contained folder GitHub Pages serves.

Writes:
  site/index.html, app.js, styles.css, vendor/    (the frontend, copied)
  site/data/screener.json                          (every ranked setup)
  site/data/ohlcv/<SYMBOL>__<tf>.json              (candles for each flagged stock)

The frontend reads these files directly — no backend. Run after bulk_load.py
(which fetches data and builds the screen cache).

Usage:  python build_site.py
"""

import json
import os
import re
import shutil
from datetime import datetime, timezone, timedelta

import db
import screener
from resample import to_weekly, to_monthly

SITE = "site"
DATA_DIR = os.path.join(SITE, "data")
OHLCV_DIR = os.path.join(DATA_DIR, "ohlcv")
RESAMPLE = {"1d": None, "1w": to_weekly, "1m": to_monthly}


def _safe(name):
    """Filename-safe symbol; MUST match safeName() in app.js."""
    return re.sub(r"[^A-Za-z0-9]", "_", name)


def main():
    if os.path.isdir(SITE):
        shutil.rmtree(SITE)
    os.makedirs(OHLCV_DIR, exist_ok=True)

    # Prefer the cache built by bulk_load; else compute live.
    candidates = screener.load_cache()
    if candidates is None:
        candidates = screener.screen_clean({s: db.read_candles(s) for s in db.list_symbols()})

    with open(os.path.join(DATA_DIR, "screener.json"), "w") as f:
        json.dump(candidates, f)

    # UI freshness stamps. `data_through` = newest price bar we actually have (the
    # real data-freshness signal); `generated_at` = when this screen/site was built.
    # IST = UTC + 5:30, so build time reads correctly locally or in the UTC Action.
    with db.connect() as con:
        data_through = con.execute("SELECT MAX(date) FROM candles").fetchone()[0]
    ist = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    with open(os.path.join(DATA_DIR, "meta.json"), "w") as f:
        json.dump({"generated_at": ist.strftime("%Y-%m-%d %H:%M IST"),
                   "data_through": data_through,
                   "setups": len(candidates)}, f)

    # One candle file per (symbol, timeframe) that appears in the results.
    pairs = sorted({(c["symbol"], c["timeframe"]) for c in candidates})
    for symbol, tf in pairs:
        daily = db.read_candles(symbol)
        rows = RESAMPLE[tf](daily) if RESAMPLE[tf] else daily
        candles = [{"time": r[0][:10], "open": r[1], "high": r[2],
                    "low": r[3], "close": r[4]} for r in rows]
        with open(os.path.join(OHLCV_DIR, f"{_safe(symbol)}__{tf}.json"), "w") as f:
            json.dump(candles, f)

    # Copy the frontend.
    for name in ("index.html", "app.js", "styles.css"):
        shutil.copy(os.path.join("static", name), os.path.join(SITE, name))
    shutil.copytree(os.path.join("static", "vendor"),
                    os.path.join(SITE, "vendor"), dirs_exist_ok=True)

    print(f"Built {SITE}/: {len(candidates)} setups, {len(pairs)} candle files.")


if __name__ == "__main__":
    main()
