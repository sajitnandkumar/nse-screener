# NSE Support/Resistance Screener

A local app to screen NSE (National Stock Exchange, India) stocks that are trading
near support/resistance lines.

## Who this is for
The owner is a product person, not a daily coder. Explanations should go slow and
explain the "why", not just the "what".

## Full project goal
1. **Store historical daily OHLCV** for NSE stocks, pulled from the Angel One
   SmartAPI.
2. **Update the data daily** (incremental refresh, not a full re-download).
3. **Screen for stocks near support/resistance** — horizontal levels or trendlines.
   Must work on daily / weekly / monthly timeframes, and rank results by setup
   quality.
4. **Web app** — show a ranked list; click a stock to open its chart with the
   detected support/resistance line drawn on it.

## Build approach
Build in thin vertical slices. Do NOT build everything at once. Each slice should
be runnable and reviewable before moving to the next.

### Slice progress
- [x] Slice 1: Pull historical daily OHLCV for a single stock (RELIANCE) and
      print it. DONE — `angel.py` (was fetch_reliance.py) logs in and prints candles
      since Jan 2020. Confirmed working against the live API.
- [x] Slice 2: Store candles in a local SQLite DB (`nse_data.db`). `db.py` holds
      storage helpers (upsert on (symbol, date) — safe to re-run).
      `store_reliance.py` fetches + saves + reads back. DONE — 1627 RELIANCE
      candles stored and confirmed end-to-end against the live API.
- [x] Slice 3: Daily incremental updates. `db.last_stored_date()` finds the
      newest stored date; `update_reliance.py` fetches only from there to today
      (falls back to full history if DB empty). `fetch_candles()` now takes an
      optional date range. DONE — confirmed: re-run added 0 duplicate days,
      DB steady at 1627 rows. `update_reliance.py` is the daily command.
- [x] Slice 4: Detect horizontal support/resistance. `levels.py` = swing-pivot
      detection (window=5) -> price clustering (1.5% tolerance) -> classify vs
      current price; ranked by touch count. `screen_reliance.py` reads DB,
      prints support/resistance with touches + distance %, flags setups within
      3%. DONE — verified on stored data (reads DB only, no login needed).
- Shared settings now live in `config.py` (EXCHANGE/SYMBOL/SYMBOL_TOKEN/
  INTERVAL) so the screener doesn't import the login SDK.

### Tuning knobs (Slice 4)
- `levels.detect_levels`: window (pivot sensitivity), tolerance_pct (how close
  prices merge into one level), min_touches (filter one-off wiggles).
- `screen_reliance.NEAR_THRESHOLD_PCT`: how close price must be to call a setup.

- [x] Slice 5: Ranked screener with 4 setup types + multi-timeframe.
      `resample.py` builds weekly/monthly candles from daily. `screener.py` is
      the engine: for each symbol x timeframe, find nearest strong level within
      NEAR_THRESHOLD_PCT (4%), classify into Resistance/Support x
      Reversal/Breakout using recent momentum (MOMENTUM_LOOKBACK bars,
      MOMENTUM_TRIGGER_PCT flip). Score = touches x proximity x timeframe_weight
      (1d=1.0, 1w=1.3, 1m=1.6). Screens all DB symbols, ranks
      by score. DONE — verified on RELIANCE across 1d/1w/1m. Engine already
      takes a list of symbols, so it scales to many stocks with no rework.

### Screening logic knobs (all in screener.py — tune after seeing output)
- NEAR_THRESHOLD_PCT=4.0 (how near price must be to a level = a setup)
- CLUSTER_TOLERANCE_PCT=1.5, MIN_TOUCHES=2 (level detection)
- MOMENTUM_LOOKBACK=3, MOMENTUM_TRIGGER_PCT=1.0 (reversal vs breakout decision)
- TIMEFRAMES windows: 1d=5, 1w=3, 1m=2; weights 1.0/1.3/1.6
- Score formula: touches * proximity * timeframe_weight

- [x] Slice 6: Bulk-load Nifty 50. `nifty50.py` = ticker list. `instruments.py`
      downloads Angel One's scrip master (cached as instruments.json, git-ignored)
      and resolves ticker -> token. `fetch_candles()` generalized to take
      symbol_token/exchange/verbose. `bulk_load.py` resolves tokens, logs in once,
      incrementally fetches+saves each stock (skips failures, rate-limited), and
      is ALSO the daily updater for the whole basket. `db.list_symbols()` added.
      DONE — user loaded 48 stocks (TATAMOTORS + LTIM don't exist in current NSE
      scrip master due to corporate actions; skipped).

- [x] Slice 5b: Screening logic v2, tuned after seeing real output.
      * Ranking is now PER-TIMEFRAME (three separate 1d/1w/1m tables) so daily's
        higher bar-count no longer buries weekly/monthly. Timeframe weight removed.
        Score = touches * proximity.
      * Reversal vs breakout now decided by CROSSING: compare price now vs price
        CROSS_LOOKBACK (5) bars ago. past below level & now above = Resistance
        Breakout; past above & now below = Support Breakdown; else held below =
        Resistance Reversal, held above = Support Reversal. (Single reference
        point, not any-wiggle-in-window, to avoid whipsaw mislabels.)
      * DIST% sign convention: Resistance Reversal +, Support Reversal -,
        Resistance Breakout - (level now below), Support Breakdown + (level now
        above). This is correct geometry, not a bug.
      * Verified on 48 stocks (via the CLI screener at the time; now web-only).

- [x] Slice 7: Local web app (FastAPI + vanilla JS + lightweight-charts).
      `app.py` serves 2 endpoints, reusing db/screener/levels/atr (no logic
      duplicated): GET /api/screener?tf=1d (ranked list) and
      GET /api/ohlcv?symbol=&tf= (candles + S/R lines + touch_points + context).
      `atr.py` = ATR(14) for volatility-normalised distance (distance_atr).
      `levels.py` now returns touch_points per level. `screener.analyze` now also
      returns role/line_type/distance_atr. Frontend in `static/`: index.html,
      app.js, styles.css, vendored lightweight-charts (no CDN/build step).
      Left pane = ranked list (symbol/setup/line/touch/ΔATR/tf), top bar = 1D/1W/
      1M toggle, right pane = candlestick chart with setup line (solid) + other
      levels (faint dashed) + touch markers + context header. Dark terminal
      aesthetic; green/red only on candles. Auto-selects top row on load.
      DONE — verified via headless screenshot (list + chart render correctly).
      Run:  ./venv/bin/uvicorn app:app --reload   then open http://127.0.0.1:8000

- [x] Slice 8: Diagonal TRENDLINE detection (the EIDPARRY-style setup).
      `trendlines.py`: swing lows/highs (with bar index) -> fit a line through
      every pivot pair -> keep lines with >= MIN_TOUCHES (3) that aren't pierced
      (MAX_VIOLATION_FRAC) -> dedupe -> strongest few. `screener.py` reworked:
      analyze_horizontal + analyze_trendline, both scored with a CAPPED touch
      count (STRENGTH_CAP=6) so trendlines aren't buried by high-touch
      horizontals; score = min(touches,CAP)*proximity (proximity-led). Each
      timeframe now yields up to 2 setups (horiz + trend), tagged. `app.py`
      /api/ohlcv now returns trendlines too + a `focus` param (which line the
      clicked row was about) driving is_setup + context. Frontend draws
      trendlines as diagonal LineSeries; deep-link params added
      (?symbol=&tf=&focus=). New `watchlist.py` (extra tickers beyond Nifty 50);
      bulk_load loads NIFTY_50 + WATCHLIST. EIDPARRY (token 916) added to
      watchlist. DONE — verified via screenshot (ICICIBANK 1w ascending support
      trendline renders correctly with touch markers + context).

### Screening logic knobs v3 (screener.py + trendlines.py)
- STRENGTH_CAP=6 (caps touch influence; raise to make line-strength matter more)
- trendlines: TREND_TOL_PCT=2.5, MIN_TOUCHES=3, MIN_SPAN_BARS=6,
  MAX_VIOLATION_FRAC=0.15; TIMEFRAMES trend_window 1d=10/1w=4/1m=2
- EIDPARRY-type "bounce off rising support" = trendline + "Support Reversal".
  Trendline "Support Breakdown" = a broken/retested support trendline.

- [~] Slice 9: Close-based clean-line engine (logic rewrite; NOT yet wired into
      the web app). All screening now on CLOSING prices. `config.yaml` +
      `settings.py` hold every knob (no hardcoding). `trendlines.detect_clean_lines`
      = close swings -> pair-fit (support from low-closes, resistance from
      high-closes) -> filters: min_touches, max_fit_atr (avg touch dist in ATR),
      max_violations (wrong-side CLOSES beyond buffer_atr), min_span. Horizontal =
      slope~0 (total move < horizontal_total_atr). `screener.screen_clean` applies
      ATR proximity gate (proximity_tol_atr=0.5), labels via side+sign, scores
      fit-first (`_clean_score`, fit floored at 0.1). `contact_sheet.py` renders
      top-N close-line charts w/ line+touches (matplotlib), forces EIDPARRY 1m +
      GRASIM 1d. ACCEPTANCE MET: EIDPARRY 1m flagged CLEAN, GRASIM 1d excluded.
      Tuning lesson: max_violations=1 killed EIDPARRY (its real support has 2
      brief close-pokes over 6y) -> set to 2.
      Envelope filter DONE: max_wrongside_atr=1.5 (reject broken lines, trend-safe
      — never penalises the respected side) + max_fit_atr_horizontal=0.08
      (horizontals must hug tighter). Removed the loose HINDUNILVR/HDFCLIFE 1m
      horizontals; EIDPARRY still CLEAN, GRASIM still excluded.
      Current config: max_fit_atr=0.22, max_violations=2, max_wrongside_atr=1.5,
      max_fit_atr_horizontal=0.08, min_span 1d120/1w50/1m18, proximity_tol_atr=0.5
      -> 56 setups pass (top 20 on sheet). `python contact_sheet.py <out.png>`.
- [x] Slice 10: Wired the clean engine into the web app. `app.py` now calls
      screener.screen_clean / detect_clean_lines (cached once per session) and
      maps to the SAME JSON shape, so the frontend was unchanged except adding a
      FIT column (index.html + app.js). List = clean shortlist sorted fit-first;
      chart draws close-based lines + touch markers. Verified via screenshot:
      EIDPARRY 1m ascending support renders correctly, list shows FIT column.
- [x] Slice 11: Polish + cleanup.
      * On-the-line dead zone: config on_line_atr=0.25; within that many ATR of
        the line => labelled Reversal (not breakdown/breakout). EIDPARRY 1m now
        reads "Support Reversal" (was "Support Breakdown" at -0.23 ATR).
      * Chart kept as CANDLES on purpose (lines are already close-based; candles
        preserve the green/red direction coding). Not switched to a close line.
      * Dead code DELETED: levels.py (gone), and screener.py trimmed to just
        _label_side_sign / _clean_score / screen_clean; trendlines.py trimmed to
        the close-based detector only (removed legacy percent-based detect_trendlines,
        _swings, _fit_lines, _dedupe + TREND_* constants). app.py + contact_sheet.py
        import cleanly. 14 .py files remain, all used.

- [x] Slice 12: Chart clutter fix. /api/ohlcv now draws ONLY the flagged setup
      line (was drawing every detected clean line -> dozens of faint dotted lines
      that also blew up the price axis when a projected line hit an extreme). No
      active setup -> no line. Removed unused CFG/detect_clean_lines imports in app.py.

- [x] Slice 13: Dropped weak SBIN-type flags by tightening fit (max_fit_atr
      0.22 -> 0.18). SBIN 1m (fit 0.214, loosest) now excluded; EIDPARRY kept
      (1m 0.173, 1w 0.051). 56 -> 45 setups.
      IMPORTANT FINDING: a RECENCY filter (max_bars_since_touch) was considered
      and REJECTED — it would kill the gold standard. Bars-since-last-touch:
      SBIN 1m=22 but EIDPARRY 1w=143, DRREDDY 1w=166, RELIANCE 1w=174. These
      long-term weekly pullbacks are exactly the wanted setup, so recency is the
      wrong lever. FIT is the real quality differentiator, not staleness.

- [x] Slice 14: Confidence score (0-100). `screener._confidence(ln)` =
      100*(weight_tight*tightness + (1-weight_tight)*count), where
      tightness=max(0,1-fit_atr/fit_ref_atr) [1.0=closes sit exactly on line],
      count=min(1,touches/target_touches). Config block `confidence:`
      (fit_ref_atr=0.18, target_touches=5, weight_tight=0.7) + `min_confidence=40`
      drops low-confidence setups. screen_clean ranks by confidence desc; replaced
      old _clean_score (removed weights/timeframe_weight from config). UI: FIT
      column -> CONF %, header shows confidence. Result: exact-touch lines top
      (HDFCBANK 1m horiz fit 0.009 = 85%), EIDPARRY 1m (loose fit 0.173) DROPPED
      (32.7% < 40). EIDPARRY 1w KEPT (68%, its weekly touches ARE tight, fit
      0.051) — correct, not a bug. 45 -> 32 setups. Tune weight_tight / target /
      min_confidence in config.yaml.
      NOTE: user no longer treats EIDPARRY as the gold standard — the 1M line's
      touches are too loose; "exact touches on close" is now the quality bar.

- [~] Slice 15: Expand universe to ALL NSE equities via NSE's EQUITY_L.csv.
      `universe.py` reads EQUITY_L.csv (SYMBOL col, all rows) — stock-only, NO
      ETFs (unlike Angel's dump). bulk_load uses load_universe() or NIFTY_50
      fallback, + watchlist; resolves via Angel master, skips/reports unresolved
      (capped print). Screening ~2000 stocks is minutes, so added a DISK CACHE:
      `screener.build_cache()` writes screen_cache.json (run at end of bulk_load);
      `screener.load_cache()`; app.py `_all_candidates()` reads the cache instantly
      (falls back to live compute if absent). screen_cache.json git-ignored.
      AWAITING: user saves EQUITY_L.csv into project dir, runs bulk_load (long,
      ~45-90 min first time, incremental + skip-failures, re-run to fill gaps),
      restarts app. Rebuild cache after config change:
      `./venv/bin/python -c "import screener; print(screener.build_cache())"`.

- [~] Slice 16: Static deploy on GitHub Pages (FREE, PUBLIC). Re-architected from
      live FastAPI to a static site rebuilt daily by GitHub Actions.
      * `build_site.py` -> ./site: copies static/ frontend + writes
        data/screener.json (all setups) + data/ohlcv/<SAFE_SYM>__<tf>.json (candles
        per flagged stock). _safe() = re.sub([^A-Za-z0-9],_) MUST match app.js safeName.
      * static/app.js REWRITTEN for static: reads data/screener.json once, filters
        by tf; row click fetches candle JSON + draws the one setup line from the
        candidate's own geometry (first_idx/last_idx/slope/value_now/touch_points).
        No /api, no focus param. index.html paths made RELATIVE (Pages serves under
        /<repo>/). app.py/uvicorn now LEGACY (only for local dynamic use).
      * .github/workflows/deploy.yml: daily cron 13:00 UTC (18:30 IST) + manual;
        installs reqs, restores nse_data.db from actions/cache, runs bulk_load
        (|| continue) + build_site, deploys ./site to Pages. Secrets: ANGEL_*.
      * requirements.txt fixed: added numpy, pyyaml (were pip-installed only);
        matplotlib noted as contact_sheet-only.
      * Verified locally: build_site -> 1113 setups / 919 candle files / 35MB;
        static site renders (top 1M = ELDEHSG 98% conf). DB=236MB/2061 symbols
        (too big to commit -> Actions cache; first run full fetch ~45-90min).
      AWAITING: user creates PUBLIC GitHub repo, commits code+EQUITY_L.csv+vendor
      (NOT .env/db/site — gitignored), adds ANGEL_* repo Secrets, sets Pages source
      = GitHub Actions, runs the workflow. Optional: seed first run via a Release
      asset to skip the long first fetch.

### Still TODO / iterate
- USER MUST run `bulk_load.py` to fetch EIDPARRY (needs login) before it appears
  in the screen — not yet in the DB.
- Scoring is now proximity-led (touches capped at 6); tune STRENGTH_CAP if
  line-strength should differentiate more.
- (Optional) expand universe beyond Nifty 50; replace TATAMOTORS/LTIM.

## Tech notes
- Data source: Angel One SmartAPI (requires API key + login credentials).
- Runs locally. Python 3.14, macOS. Virtualenv in `venv/`.
- Housekeeping (2026-07-24): deleted the per-slice demo scripts
  (store_reliance/update_reliance/screen_reliance) and the CLI `run_screener.py`
  (superseded by the web app). Renamed `fetch_reliance.py` -> `angel.py` (the
  login/fetch client; `python angel.py` is a connection smoke test).
- Secrets live in `.env` (git-ignored): ANGEL_API_KEY, ANGEL_CLIENT_CODE,
  ANGEL_MPIN, ANGEL_TOTP_SECRET. Login uses MPIN + auto-generated TOTP.
- smartapi-python has undeclared deps: `logzero` and `websocket-client` must be
  installed manually (already in requirements.txt).
- Angel One daily-candle requests cap at 2000 candles, so date ranges are
  fetched in chunks (~1800 days) and stitched together.
- Instruments are identified by a numeric symbol token, NOT the ticker name.
  RELIANCE-EQ (NSE) = token 2885. Slice 2+ should look tokens up from Angel
  One's instrument master list instead of hardcoding.
