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
      DONE & DEPLOYED (2026-07-24). LIVE: https://sajitnandkumar.github.io/nse-screener/
      Repo: github.com/sajitnandkumar/nse-screener (PUBLIC). 1113 setups live.

- [x] Slice 17: UX + reliability upgrade (2026-07-27).
    (1) Chart Candles/Line toggle (in chart header; keeps zoom on toggle — only a
        new stock selection refits). app.js: mainSeries built per state.chartType;
        loadChart() fetches+stores, drawChart(fit) renders.
    (2) LTP (last close) shown in the list + chart header. screener emits `close`.
        Dropped the redundant list TF column (list is already filtered to the tf).
    (3) Reliability filters in a `reliability:` block in config.yaml, applied in
        screener.screen_clean (gates) + _confidence (booster):
        - LIQUIDITY GATE (per stock, on daily data): avg ~20d traded value
          (close x volume) >= min_turnover_cr (₹5cr). Biggest noise-remover.
          _turnover_cr(); emitted as `turnover_cr`.
        - VOLUME CONFIRMATION: breakout/breakdown REQUIRE recent volume expansion
          (vol_ratio >= vol_confirm_mult=1.5); reversals get a confidence booster
          only. vol_ratio = MAX vol over last vol_recent_bars / mean of prior
          vol_base_bars (MAX is robust to a partial current weekly/monthly bar).
          _vol_ratio(); emitted as `vol_ratio`; shown as `Vol×` column (green ≥1.5).
        - RECENCY: skip lines whose last touch is stale per tf (max_stale_bars).
          bars_since = last_idx - max(touch idx); emitted as `bars_since_touch`.
        - DISPERSION: touch span (max-min touch idx) >= min_touch_span_frac(0.5) x
          min_span_bars — touches must spread across time, not cluster.
        Confidence formula now: 100*(w_tight*tightness + w_count*count + w_vol*vol_boost)
        where w_vol=weight_vol(0.2) reserved from geometry ONLY when vol data exists
        (missing volume -> geometry keeps full weight, no penalty).
        NOTE: after this, screener.json rows carry close/turnover_cr/vol_ratio/
        bars_since_touch — must rebuild cache + site (skip_fetch=true) to populate.

- [x] Slice 18: "Purist" tightness + two S/R bug fixes (2026-07-27).
    TIGHTNESS (config.yaml): touch_tol_atr 0.6->0.3, max_fit_atr 0.18->0.06,
      max_fit_atr_horizontal 0.08->0.03, confidence.fit_ref_atr 0.18->0.06,
      weight_tight 0.7->0.8. Only near-exact lines survive (avg deviation ~0.02
      ATR). Side effect: most survivors have exactly 3 touches (near-zero
      deviation + many touches is rare). Sweep showed near-exact line COUNT peaks
      around tol0.4/fit0.10 then plateaus — tightening past that mainly trims count.
    BUG 1 (drawing): a shallow-sloped line tagged "horizontal" (total move just
      under horizontal_total_atr) was drawn FLAT at value_now via createPriceLine,
      so its earlier touches floated above the flat line. FIX: app.js drawChart now
      draws EVERY line (horiz + trend) through its true geometry (LineSeries
      endpoints from slope), lastValueVisible for the axis tag. Markers now land on
      the line. (DHANBANK 1d: touches 36.42->35.88->34.42, drawn flat at 34.24.)
    BUG 2 (logic): cleanliness was only checked from the FIRST TOUCH forward, so a
      horizontal level price traded far past BEFORE the touch window still passed
      (DHANBANK "resistance" 34.24 had closes to 45.77 / 47 days >5% above it in
      2020-2024; FORCEMOT "support" had price 31.9 ATR below it). FIX:
      trendlines._fit_clean computes hist_wrongside_atr = worst wrong-side close vs
      the flat level (value_now) over the FULL history; detect_clean_lines rejects
      HORIZONTALS whose hist_wrongside_atr > max_hist_wrongside_atr_horizontal
      (1.5, new config knob). Horizontals only — a trendline legitimately exists
      only over its span, and back-projecting its slope across all history is
      meaningless (that naive test falsely flagged 59; horizontal-only flagged 14
      -> removed 10 real false levels). Result: 138 -> 128 setups, trendlines
      untouched, DHANBANK/FORCEMOT/GMRP&UI/BIOCON false horizontals gone.

- [x] Slice 19: CONTAINMENT filter — "price must HUG the line" (2026-07-27).
      User flagged INDIAGLYCO 1w (conf 94%, fit 0.003): touches were pristine but
      3 clustered in 2021-22 + 1 in 2026 across a 4-year void, and price dipped
      5.7 ATR BELOW the resistance in between — a slope through empty space, not a
      respected boundary. Root cause: fit_atr only measures TOUCH distance; nothing
      measured how far the REST of price strayed. Investigated max-gap-between-
      touches (rejected — ~1.0 for 126/128, structural: lines are old-cluster + 1
      recent touch). Right lever = far-side excursion: for each line, the deepest
      close on the OPEN side (below a resistance / above a support) over its span.
      trendlines._fit_clean computes max_farside_atr; detect_clean_lines rejects any
      line (horiz + trend) with max_farside_atr > CFG max_farside_atr (new knob=4.0).
      screener emits max_farside_atr. Result 128 -> 21 (all survivors <=3.99 ATR
      far-side); INDIAGLYCO/BALKRISIND(24.5)/SHAKTIPUMP(23.1)/DBCORP(15.9) all gone.
      Confidence ceiling fell 94%->74% — CORRECT: the 90%+ lines scored high on
      touch-tightness but were exactly the wild lines. All survivors 1w/1m (daily
      has more bars, more chance to stray). Tune: max_farside_atr 4->5 ~31 setups,
      ->3 ~12. This SUPERSEDES EIDPARRY-style "big rally off rising support" — user
      now wants price coiled tight around the line, not trending far away from it.

- [x] Slice 20: "No wrong-side crossing between touches" + per-tf containment
      (2026-07-27). User flagged JAMNAAUTO 1w (avg-dist 0.9 = hugs line, normal
      slope — clean by every metric) with the real rule: "between two touches on
      the support line, the price crossed BELOW the line." I.e. a valid line must
      be RESPECTED between its touches (support never closes below, resistance
      never above). Also "1D has 0 setups": the old single max_farside_atr=4 cap
      was span-dependent — daily lines span 120+ bars so stray further in ATR than
      ~18-bar monthly lines, so a global cap deletes ALL daily. Fixes:
      * VIOLATIONS now counted strictly BETWEEN first & last TOUCH (was first-touch
        -> now), so the post-last-touch current region is judged by the LABEL
        (reversal vs break), not rejected. max_violations 2->0, buffer_atr 0.5->0.25
        (a "decisive break"; buffer 0 is too strict — closes wiggle a hair off).
        trendlines._fit_clean: lt=touch_idx.max(); violations/wrongside over
        [first,lt]; far-side over [first,now].
      * CONTAINMENT (max_farside_atr) is now PER-TIMEFRAME {1d:8,1w:5,1m:4} and the
        gate moved from detect_clean_lines to screener.screen_clean (which knows
        tf). detect_clean_lines no longer gates far-side.
      Result: 21 -> 24 setups, 1d=11/1w=8/1m=5 (all tabs populated), JAMNAAUTO +
      INDIAGLYCO both gone, verified 0 wrong-side crossings among all survivors.
      Tune: max_violations (0=strict), buffer_atr, per-tf max_farside_atr.

- [x] Slice 21: Reversal must hold the line AFTER the last touch too (2026-07-27).
      User flagged ELGIEQUIP + INDUSINDBK 1d Resistance Reversals: price crossed
      ABOVE the line after the last touch (26 and 5 bars) then came back, so
      "holding below resistance" was false. Rule: for a REVERSAL, price must stay
      on the correct side from the last touch to NOW, not just between touches.
      screener._respects_after_touch(rows, ln, atrv, buffer_atr): from last-touch
      idx to end, reject if any close is > buffer_atr on the wrong side (support
      closed below / resistance above). Applied only to Resistance/Support Reversal
      (breakouts/breakdowns are EXEMPT — crossing the line IS their setup). Result:
      24 -> 10 setups (1d=2/1w=4/1m=4); ELGIEQUIP/INDUSINDBK gone; verified all 5
      reversal survivors hold their side post-touch. List is now very exclusive
      (10 of ~2000) — quality over quantity, matches the user's stated bar.

- [x] Slice 22: TRENDLINE DETECTOR REWRITTEN on an exact convex-hull definition
      (2026-07-28). Discarded the fit-and-filter approach. Three rules: (1) lines
      anchored on CLOSES; (2) between a line's two anchors NO close is on the wrong
      side; (3) most recent touch within recency_days (10 calendar). Rule 1+2 ARE
      the convex hull: LOWER-hull edges = support (nothing closes below between
      anchors, by construction), UPPER-hull edges = resistance. No regression, no
      violation-filtering — exactness is structural.
      * `hull_lines.py` NEW: Andrew's monotone chain on (bar_index, close), on a
        trailing per-tf WINDOW (hull.lookback {1d:750,1w:null,1m:null}) so recent
        structure isn't hidden beneath older global extremes. Each edge -> extend to
        now, count touches within touch_tol_atr(0.25), keep if touch_count>=
        min_touches AND newest touch within recency_days. Returns side/slope/
        line_type/touch_count/anchor+touch points/value_now/dist_now_atr.
      * `verify_hull.py` NEW: renders detected lines for 10 sample symbols to a
        self-contained hull_verify.html (candles + line + anchor/touch markers).
        User reviewed & approved. Automated check: 0/53 lines had any wrong-side
        close between anchors (guarantee holds).
      * `screener.py` REWRITTEN to run on detect_hull_lines. Kept: LIQUIDITY gate,
        volume context, setup labelling (_label_side_sign). Confidence is now
        touch-count-LED (cleanliness is guaranteed): _confidence(touch_count,
        fit_atr, vol_ratio) = 100*(0.7*count + 0.3*tight + vol), count=min(1,
        touches/target_touches), tight=1-fit/touch_tol. Dropped from the pipeline
        (superseded by rules 1-3): proximity gate, far-side containment, dispersion,
        bars_since recency, post-touch respect, violation counting. screen_clean
        signature unchanged so build_site/app.py/bulk_load are untouched.
      * KEY PROPERTY: the hull's most recent edge always passes through TODAY, so
        ~every liquid stock has a support+resistance line "touching now" -> the raw
        3-rule set is huge (5953 across 1166 symbols; a proximity gate barely helps).
        The real strength dial is min_touches. User chose min_touches=6 + a 50%
        confidence floor; target_touches raised 5->10 so ranking spreads (else all
        >=5-touch lines tie). Result: 509 setups (1d256/1w171/1m82), touch 6-27,
        conf 50-93.8, ranked strongest-first. Frontend UNCHANGED (same JSON shape).
      * trendlines.py kept (untouched) — now used ONLY by the legacy contact_sheet.
        Old config keys (timeframes/touch_tol_atr/max_fit_atr/max_violations/
        max_farside_atr/etc.) remain for contact_sheet; the live path uses the
        `hull:` + `reliability:` + `confidence:` blocks. NOT yet deployed — awaiting
        user OK on the 509-list before pushing live.
    * Horizontal-vs-trend label fix: classify on the line's TOTAL price change over
      its drawn extent (first anchor -> now) in ATR (hull.horizontal_total_atr=0.5),
      NOT total-move-between-anchors (mislabels short-steep lines like SOUTHWEST) and
      NOT slope-per-bar (mislabels long-gentle lines like CIEINDIA). 490 trend / 19
      horizontal; all horizontals verified genuinely flat (<0.5 ATR total move).
    * Freshness stamps: build_site.py writes site/data/meta.json {generated_at
      (IST = UTC+5:30, cloud-correct), data_through (= MAX candle date in DB, the
      real data-freshness signal), setups}; static/app.js loadMeta() shows
      "data through <date> · built <ts>" in the top bar. Missing meta = silent no-op.
      (generated_at alone was misleading — it's build time, not fetch time.)
    * CLEANUP before deploy: DELETED trendlines.py (old fit-and-filter detector,
      superseded by hull_lines.py) and contact_sheet.py (matplotlib dev tool, sole
      user of trendlines — superseded by verify_hull.py). Removed matplotlib + numpy
      from requirements.txt (numpy was only used by trendlines; hull_lines is pure
      Python). config.yaml trimmed to ONLY live keys (hull/on_line_atr/confidence/
      min_confidence/reliability) — dropped all old-detector keys (timeframes,
      touch_tol_atr, buffer_atr, proximity_tol_atr, min_touches, max_fit_atr,
      max_violations, max_wrongside_atr, max_fit_atr_horizontal,
      max_hist_wrongside_atr_horizontal, top-level horizontal_total_atr,
      max_farside_atr, top_n) and dead reliability keys (volume_confirmation,
      recency, max_stale_bars, dispersion, min_touch_span_frac). hull_verify.html
      gitignored. KEPT: config.py (used by angel.py), verify_hull.py (line-inspection
      tool), app.py + fastapi/uvicorn (legacy local server, imports clean, inert for
      deploy). 16 .py files remain, all import OK; build_cache+build_site verified.

- [x] Slice 23: CONF redefinition + filter bar + sorting + dedup fix (2026-07-28).
    1. CONF is now a transparent line-QUALITY score (screener._conf_components):
       CONF = 100*(0.35*touch + 0.35*fit + 0.15*span + 0.15*recency), each 0-1.
       touch=min(touches,touch_cap)/touch_cap; fit=1-min(fit_atr/fit_cap,1);
       span=min(span_DAYS/span_cap_days,1) [calendar days, NOT bars -> no tf bias,
       monthly lines score full span]; recency=linear decay of days_since over
       recency_window. Proximity(dist_atr) + volume DELIBERATELY EXCLUDED (own
       columns). Config block `confidence:` (weights + touch_cap10/fit_cap0.25/
       span_cap_days365/recency_window14). Backend min_confidence floor REMOVED
       (UI filter handles it). candidate now carries conf_parts + span_days +
       days_since_touch.
    2. Filter bar (static/index.html #filter-bar + app.js setupFilters): live
       ΔATR<=(0.5) / Touch>=(6) / Conf>=(80) / ₹cr>=(5) inputs + setup chips
       (All/Support Reversal/Resistance Reversal/Breakouts) + "N of M shown".
       Backend liquidity gate lowered 5cr->2cr so the turnover filter has range
       (UI default 5cr). Defaults show 8/23/26 setups on 1d/1w/1m.
    3. Sorting: COLUMNS-driven thead, click-to-sort asc/desc with ▲/▼ arrow,
       default CONF desc; numeric cols right-aligned monospace (already via CSS).
    4. Dedup bug: hull_lines.py had NO dedup (old trendlines._dedupe_clean was
       dropped) + every hull edge is extended to now, so adjacent lower/upper-hull
       vertices near the last bar spawned near-identical parallel lines (BLUESTONE
       1d had 2 support edges: value 617.15/618.10, slope 4.72/4.76). Fix in
       screener.screen_clean: collapse to ONE line per (symbol, timeframe, side) =
       highest (confidence, touches). 771 -> 708 setups; verified 0 (sym,tf,side)
       has >1 row. NOT yet deployed (committed; redeploy pending user OK).
     NOTE: Slice 23 (CONF/filter/sort/dedup) IS deployed live (commit 346bfb8,
     skip_fetch run 30304857630 succeeded 2026-07-28; seed data ~Jul 24).

- [~] Slice 24: BACKTEST engine + summary UX (2026-07-28). Does the screener have
      edge / is CONF predictive? NOTE: no backtest existed before — built it.
      * `backtest.py` — WALK-FORWARD, honest as-of (hull detected only on data up
        to each as-of date via detect_hull_lines(rows[:t+1]) — no lookahead). When
        price is within proximity_atr of a line, record the setup + as-of CONF, then
        scan forward once to fb_max and store the first BREACH OFFSET per move_atr in
        the sweep grid (config backtest.sweep.move_atr[0.5,1,1.5] x forward_bars
        [20,40,60]). Reversal setups only (v1). Non-overlap gap = default fb; loop
        leaves fb_max room (no censoring). Outcome = "line held as boundary" i.e.
        HELD iff no close breached by >move_atr within forward_bars (a SURVIVAL test).
        Writes backtest_results.json (~36.7k instances, 2021-03 -> 2026-04).
      * `sweep.py` — prints the 3x3 grid (overall + per-CONF-bucket staircase + mono
        flags + top-bucket merge). FINDINGS: staircase monotonic in populated bands
        across ALL 9 cells (ranking robust). Overall never clears 50% (max 32% at
        1.5ATR/20bar). Top band clears 50% ONLY at 1.5/20 (58%). Survival test =>
        LONGER horizon LOWERS hold rate (counterintuitive; move_atr is the real lever).
      * `build_backtest.py` -> site/backtest.html + site/data/backtest.json (compact:
        per-instance breach offsets, so the client derives HELD/BROKE for any cell).
      * UX (static/backtest.html + backtest.js) Panels 1+2: verdict scorecard +
        CONF calibration bars, with LIVE move_atr/forward_bars chips (instant
        re-aggregation off breach offsets). CONF bands = <70/70-79/80-84/85-100 (top
        merged; old 90-100 was thin n~55 -> 85-100 n~703). Bands n<100 flagged
        "thin · low-trust". Verdict DERIVED: leads with ranking-validated (monotonic),
        frames edge as definition-dependent (never "no edge" from one definition).
      * Panel 3 (breakdown table: setup/line/touch-band/timeframe, sortable, respects
        sliders) + Panel 4 (coverage/honesty: n everywhere, n<100 dimmed+"thin",
        walk-forward disclosure) DONE. Breakdown insight: more touches = higher hold
        (13+ =46%), Support Rev (27%) > Resistance Rev (20%), horiz > trend.
      * COVERAGE GAP found + disclosed in Panel 4: 1M has 0 instances — the up-to-60
        forward window exceeds ~72 monthly bars (loop needs len-fb_max room). Backtest
        covers 1D+1W only; monthly needs a PER-TIMEFRAME forward horizon (TODO).
      * DEFINITION FIXES DONE (both changed the verdict a lot):
        - PER-TIMEFRAME horizons config backtest.horizons {1d:[20,40,60], 1w:[4,9,13],
          1m:[1,2,3]} = ~1/2/3 months each. 1M NOW COVERED (0 -> 3510 instances;
          total 37417). UI horizon control = Short/Med/Long (per-tf bars).
        - ENDPOINT mode alongside SURVIVAL. Engine records per instance: fbo (first
          wrong-side breach offset per move -> survival) + wd (wrong-side ATR at each
          horizon bar -> endpoint). UI mode toggle Survival/Endpoint. held(): survival
          = fbo[move] None or > horizons[tf][level]; endpoint = wd[level] <= move.
        FINDINGS: default (survival/1.0/med) staircase 15.4/43.0/49.4/51.5 — monotonic
        AND top band 85-100 (n=939) CLEARS 50%. Endpoint >> survival at long horizon
        (top band long: survival 45% vs endpoint 67%) — confirms survival suppresses
        long windows. Earlier "no edge" was an artifact of daily-centric 20-bar horizon
        + missing weekly/monthly. build_backtest.py compact rows carry b(=fbo)/wd/tf;
        meta carries moves/horizons/levels/def_mode. sweep.py is now STALE (old breach
        dict) — superseded by the interactive page.
      * Panel 5 (drill-down) DONE: click a CONF bar or breakdown row -> instance list
        (sym/as-of/CONF/HELD-BROKE/bars-to-resolve, sorted by CONF, cap 300) -> click
        an instance -> lightweight-charts candles at the as-of date with the S/R line
        (fi..li+H geometry) + a ↓ as-of marker (verified candle[li].time == as_of_date).
        Outcomes/labels re-compute live with the mode/move/horizon controls. Needs
        per-instance geometry (fi/li/sl/vn/sd/sym added to compact rows) + candle files:
        build_backtest.py now emits site/data/ohlcv/<safe>__<tf>.json for all backtest
        (symbol,tf) pairs (3147 files) + copies vendor. backtest.json ~9.2MB, 37417 rows.
      * BACKTEST UX COMPLETE (Panels 1-5). Still LOCAL only — NOT wired into the
        deploy/GitHub Action (build_site.py doesn't build the backtest; would need the
        Action to run backtest.py which is ~5min + heavy). To view:
        `python backtest.py && python build_backtest.py` then serve site/ -> /backtest.html.
        sweep.py is STALE (old breach dict). Reversal setups only (breakouts = v2,
        need an inverted follow-through outcome rule).

- [x] Slice 27: CLOSE THE LOOP — travel cap + backtest-driven screener filter
      (2026-07-28). (1) hull_lines: reject lines whose total travel over their extent
      > hull.max_travel_atr (12) — kills trend-envelope junk (GANESHHOU = upper hull
      of a 65x uptrend, ~40 ATR travel). total_move_atr was already computed for the
      horiz/trend split, so the cap is one line. Live screener 708 -> 638, max travel
      exactly 12; backtest 44412 -> 38992, verified 0 instances over 12 ATR (as-of
      ATR). Expectancy nudged UP (Support Rev ALL +3.5 -> +3.9%@14). (2) Screener:
      added an opt-in "Rev% >=" filter (state.filters.minRev, passesFilters uses
      bandHold(c).rev) — backtest reversed-rate drives live filtering. Shown only when
      the summary is loaded. NOTE: hit a STALE-results ghost (a prior bg run wrote
      pre-cap output); verified the cap via a live _backtest_symbol_tf call then did a
      clean pkill+re-run. Lesson: always confirm backtest_results.json freshness
      (max-travel check) after a re-run. Still LOCAL only.

- [x] Slice 26: BACKTEST REMODELLED to reversal/break + FORWARD RETURNS (2026-07-28,
      user's methodology). Replaced survival/endpoint binary with: at each as-of setup,
      REVERSED vs BROKE (broke = close >break_buffer_atr(0.5) past the line within
      classify_window(14) bars) + signed CLOSE-to-close % return at return_bars [1,5,14].
      config backtest: return_bars/break_buffer_atr/classify_window (dropped move_atr
      grid/horizons/modes). backtest.py._forward records rets[] + break_bar. UX
      (backtest.html/js) rebuilt: P1 verdict cards (reversed% + expectancy@featured),
      P2 outcome&returns table (reversed/broke/all x @1/5/14 avg+median), P3 CONF-band
      predictiveness (rev% + move by band, per category), P4 breakdown (tf/line/touch),
      P5 drill-down (outcome + rets + chart at as-of). Featured-horizon chips (1/5/14).
      FINDINGS (44,412 instances): Support Reversal reversed 22%/broke 78%, reversed
      +18.6%@14 vs broke -0.8% -> ALL +3.5%@14 (POSITIVE edge via ASYMMETRY: small
      losses, big wins — NOT hit-rate). Resistance Reversal reversed 18%, mostly break
      UP (+5.6%) -> ALL +2.9% (weak as a short). CONF predictive: reversed% rises with
      CONF within every tf. Screener surfacing updated: Hist% -> "Rev%" (reversed rate
      for setup x tf x band) + header "reversed X%, avg move @14 +Y%". build_backtest
      _write_summary now {cat: {setup: {tf: {band: {n,rev,move[]}}}}}. Local only.
      TODO still open: GANESHHOU-type trend-envelope lines (travel cap); breakouts v2.

- [~] Slice 25: SURFACE the backtest on the main screener (2026-07-28).
      * build_backtest.py._write_summary -> backtest_summary.json (ROOT, ~500 bytes,
        COMMITTED not gitignored): per (timeframe x CONF band) hold-rate + n at the
        DEFAULT def (survival/1.0/med). backtest_results.json now gitignored (20MB).
      * build_site.py: if backtest_results.json present -> build_backtest.main()
        (full page into site/); always copy backtest_summary.json into site/data/ and
        stamp `page` = does site/backtest.html exist (so the link only shows when the
        page is actually deployed, never 404s).
      * Screener (static/index.html + app.js): loads data/backtest_summary.json;
        adds a "Hist%" column = the setup's CONF-band backtested hold rate for its tf
        (green >=50, dim if n<100 or missing), a chart-header "this CONF band held
        X% (n=..)" line, and a "Backtest ↗" topbar link (shown only if SUMMARY.page).
        Column/link degrade gracefully if the summary isn't shipped.
      * FINDING (default survival/1.0/med, per tf): 1D 9/22/26/30%, 1W 34/48/52/51%,
        1M 82/85/91/88% — CONF ranks correctly WITHIN each tf; cross-tf gap is large
        and DEFINITION-sensitive (1M's high rate ~ short-in-ATR 2-month horizon).
      * DEPLOY STATUS: local build shows link+Hist%+full page. Cloud: commit
        backtest_summary.json + static/backtest.* + backtest.py/build_backtest.py ->
        Hist% goes live from the committed summary; full drill-down page NOT in cloud
        (no backtest_results.json there) so link stays hidden live. NOT yet committed/
        deployed.

### Deployment ops (GitHub Pages + Actions) — how it actually works
- Repo PUBLIC (free unlimited Actions + Pages). Code+EQUITY_L.csv+static/vendor
  committed; .env/nse_data.db/screen_cache.json/instruments.json/site/ gitignored.
- Secrets (repo → Settings → Secrets → Actions): ANGEL_API_KEY, ANGEL_CLIENT_CODE,
  ANGEL_MPIN, ANGEL_TOTP_SECRET. Pages source = GitHub Actions.
- Workflow `.github/workflows/deploy.yml`: daily cron 13:00 UTC (18:30 IST) +
  manual (workflow_dispatch, has `skip_fetch` boolean input). Steps: checkout,
  py3.12, pip install, restore DB (actions/cache), SEED DB from `db-seed` release
  if no cache OR skip_fetch=true, run bulk_load (|| continue) or build_cache,
  build_site, deploy ./site to Pages.
- DB SEED: nse_data.db (248MB, 2061 stocks) uploaded as a GitHub RELEASE asset
  tagged `db-seed` (repo file limit is 100MB so DB can't be committed; releases
  allow 2GB). The cloud downloads the seed instead of cold-fetching ~2000 stocks
  (Angel rate-limits that hard). Refresh baseline occasionally:
    bulk_load.py (local) then  gh release upload db-seed nse_data.db --clobber
- Fast rebuild from seed (no fetch): Actions → Run workflow → tick skip_fetch
  (or `gh workflow run deploy.yml -f skip_fetch=true`). ~3-5 min.

### Deployment gotchas hit & fixed (don't reintroduce)
- instruments._download_master: large ~35MB file drops mid-download
  (IncompleteRead) -> now uses requests + retry + json-validate before caching.
- Angel HISTORICAL API rate-limits a 2000-stock burst ("exceeding access rate").
  bulk_load now FAST-SKIPS rate-limited stocks + circuit-breaker aborts fetch
  after 25 consecutive rate errors (earlier a 15s/30s backoff caused a multi-HOUR
  crawl — removed). Daily incremental of ~2000 stocks is inherently ~1hr and may
  throttle; if chronic, re-seed instead of relying on cloud fetch.
- Failed runs cached a PARTIAL DB; the seed step only downloaded when no file
  existed, so the junk cache won -> only 17 setups. Fix: skip_fetch force-downloads
  seed (--clobber); deleted polluted caches (gh cache delete).
- requirements.txt was missing numpy+pyyaml (pip-installed only) -> added; would
  have broken the Action.

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
