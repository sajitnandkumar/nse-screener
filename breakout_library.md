# Breakout Agent Library: Definitions and Formulas

Seven true breakouts, each defined for four segments. A breakout here means price closing beyond a defined level or range. Trend signals (EMA, Supertrend, VWAP), momentum (RSI), volume and options-flow signals are not breakouts and are out of scope for this document.

---

## 1. Opening Range Breakout (ORB)

**What it is.** The high and low of the first N minutes form a box. A close outside the box suggests the day's direction has been set.

**Why it helps.** The opening minutes absorb overnight news and order imbalance. A decisive break of that range, especially a wide one on strong volume, has historically had better-than-random follow-through on liquid Indian instruments.

**Fires / invalidates.** Fires on a 5-minute bar *close* beyond the range (a touch does not count), once per side per session. Invalid if price closes back at the opposite side of the range (or its midpoint for a tighter stop).

**Base-rate success.** Price reaches trigger + 1R before the invalidation level, where R = distance from trigger to invalidation. Horizon: same session.

**Worked example (MAZDOCK, Mazagon Dock Shipbuilders, long)**

| Item | Value |
|---|---|
| Opening range | High ₹2,842.00, low ₹2,806.50 |
| Breakout fires (5m close) | ₹2,845.50 = trigger |
| Invalidation (opposite side of range) | ₹2,806.50 |
| R = trigger - invalidation | ₹39.00 |
| Success target = trigger + 1R | ₹2,884.50 |

Price reaches ₹2,884.50 before ₹2,806.50 in the session: success. Price hits ₹2,806.50 first: failure.

**Terms used**

| Term | Meaning | Formula / default |
|---|---|---|
| `H`, `L`, `C` | High, low, close of a bar | |
| `C_5m,t` | Close of the current 5-minute bar | |
| `τ` | Current time of day (IST) | No new intraday triggers after 14:45 |
| `b` | Breakout buffer | Default 0.1% of price |
| `DATR` | Daily ATR, in price units (₹ or index points) | `ATR(14)` on daily bars |
| `RVOL_τ` | Time-of-day relative volume | `CumVol_today(9:15 → τ) / avg CumVol(9:15 → τ), last 20 sessions` |

RVOL is time-of-day adjusted because comparing 9:45 volume with a full-day average makes every early move look weak.

### Long-term investing
Not applicable. ORB is an intraday concept.

### Short-term (swing)
Not applicable. ORB is an intraday concept.

### Intraday stock (5-min bars, cash stock)

| Parameter | Rule |
|---|---|
| Window | 9:15 to 9:15 + W, where W = 5, 15 or 30 min (default 15) |
| ORH | `max(H)` of the window bars |
| ORL | `min(L)` of the window bars |
| ORW | `ORH - ORL` |
| Width filter | `0.25 x DATR ≤ ORW ≤ 0.8 x DATR` |
| Long | `C_5m,t > ORH x (1 + b)` and `RVOL_τ ≥ 1.5`, before 14:45 |
| Short | `C_5m,t < ORL x (1 - b)` and `RVOL_τ ≥ 1.5`, before 14:45 |

The width filter matters: tiny opening ranges produce breaks that mean nothing; huge ones leave no room to run.

### F&O (continuous front-month futures)

Same rules as intraday stock, run on the continuous front-month futures series (range or levels, trigger bar and volume all from futures). Only the differences:

| Difference | Rule |
|---|---|
| Instruments | NIFTY, BANKNIFTY, SENSEX or stock futures |
| Width filter units | DATR of the futures, in points |
| Rollover | Use the contract that is front-month at 9:15; never switch mid-session |

---

## 2. Previous High / Previous Low (D / W / M)

**What it is.** The prior period's high and low are the most-watched levels. A close beyond them suggests buyers or sellers have taken control.

**Why it helps.** These levels cluster stop-losses and pending orders, so a genuine break often triggers a run. With a volume filter it separates real breaks from stop hunts.

**Fires / invalidates.** Fires on a bar *close* beyond the level, once per level per period; re-arms after a close back inside. Invalid at the low of the breakout bar for longs (high of the breakout bar for shorts).

**Base-rate success.** Price reaches trigger + 1R before invalidation (R = trigger to invalidation distance). Horizon: same session (intraday, F&O), 10 sessions (swing), 13 weeks (long-term).

**Worked example (RELIANCE, intraday, long)**

| Item | Value |
|---|---|
| Previous day high (PDH) | ₹1,418.00 |
| Breakout bar (5m) | Close ₹1,420.10, low ₹1,413.20 |
| Trigger | ₹1,420.10 (above ₹1,418.00 x 1.001 = ₹1,419.42) |
| Invalidation (low of breakout bar) | ₹1,413.20 |
| R = trigger - invalidation | ₹6.90 |
| Success target = trigger + 1R | ₹1,427.00 |

Price reaches ₹1,427.00 before ₹1,413.20 in the session: success. Price hits ₹1,413.20 first: failure.

**Terms used**

| Term | Meaning | Formula / default |
|---|---|---|
| `H`, `L`, `C`, `V` | High, low, close, volume of a bar | |
| `_M`, `_W`, `_D` | Monthly, weekly, daily bar | |
| `t-1` | Previous bar of that timeframe | e.g. `H_D,t-1` = yesterday's high |
| `C_5m,t` | Close of the current 5-minute bar | |
| `τ` | Current time of day (IST) | No new intraday triggers after 14:45 |
| `b` | Breakout buffer | Default 0.1% of price |
| `RVOL_D` | Daily relative volume | `V_D,t / SMA(V_D, 50)` |
| `RVOL_W` | Weekly relative volume | `V_W,t / SMA(V_W, 20)` |
| `RVOL_τ` | Time-of-day relative volume | `CumVol_today(9:15 → τ) / avg CumVol(9:15 → τ), last 20 sessions` |

### Long-term investing (weekly bars)
Previous month high/low, weekly close:

| Parameter | Rule |
|---|---|
| Levels | `PMH = H_M,t-1`, `PML = L_M,t-1` |
| Long | `C_W,t > PMH x (1 + b)` and `RVOL_W ≥ 1.5` |
| Short | `C_W,t < PML x (1 - b)` |

### Short-term (swing) (daily bars)
Previous week high/low, daily close:

| Parameter | Rule |
|---|---|
| Levels | `PWH = H_W,t-1`, `PWL = L_W,t-1` |
| Long | `C_D,t > PWH x (1 + b)` and `RVOL_D ≥ 1.5` |
| Short | `C_D,t < PWL x (1 - b)` and `RVOL_D ≥ 1.5` |

### Intraday stock (5-min bars, cash stock)

| Parameter | Rule |
|---|---|
| Levels | `PDH = H_D,t-1`, `PDL = L_D,t-1` |
| Long | `C_5m,t > PDH x (1 + b)` and `RVOL_τ ≥ 1.5`, before 14:45 |
| Short | `C_5m,t < PDL x (1 - b)` and `RVOL_τ ≥ 1.5`, before 14:45 |
| Skip | If today's open is already beyond PDH/PDL (that is a gap, see #7) |

### F&O (continuous front-month futures)

Same rules as intraday stock, run on the continuous front-month futures series (range or levels, trigger bar and volume all from futures). Only the differences:

| Difference | Rule |
|---|---|
| Rollover day | Take PDH/PDL from the new front-month contract's own prior-day bar, not the stitched series (the stitch mixes two contracts) |

---

## 3. CPR Breakout (Central Pivot Range)

**What it is.** Three levels from the prior period's high, low and close. A narrow CPR is widely believed in India to precede a trending session. The breakout is a close above the top of the range (TC, Top Central level) or below the bottom (BC, Bottom Central level), with the pivot (P) in between.

**Why it helps.** CPR compresses the prior period into a value zone. Breaking out of a narrow zone is the setup; the base-rate card tests how often the "narrow CPR means trend day" belief actually holds.

**Fires / invalidates.** Fires on a bar *close* beyond TC or BC, once per side per period. Invalid at the opposite side of the CPR (BC for longs, TC for shorts), mirroring ORB.

**Base-rate success.** Price reaches trigger + 1R before invalidation (R = trigger to invalidation distance). Horizon: same session (intraday, F&O), 10 sessions (swing), 13 weeks (long-term).

**Worked example (NIFTY futures, intraday, long)**

| Item | Value |
|---|---|
| Prior day H, L, C | 25,180 / 25,020 / 25,130 |
| P = (H + L + C) / 3 | 25,110 |
| BC = (H + L) / 2 | 25,100 |
| TC = 2P - BC | 25,120 |
| CPR width | 20 / 25,110 = 0.08% (narrow) |
| Trigger (5m close) | 25,148 (above 25,120 x 1.001 = 25,145) |
| Invalidation (BC) | 25,100 |
| R = trigger - invalidation | 48 points |
| Success target = trigger + 1R | 25,196 |

Price reaches 25,196 before 25,100 in the session: success. Price hits 25,100 first: failure.

**Terms used**

| Term | Meaning | Formula / default |
|---|---|---|
| `H`, `L`, `C`, `V` | High, low, close, volume of a bar | |
| `_W`, `_D`, `_5m` | Weekly, daily, 5-minute bar | |
| `t` | Current bar | |
| `τ` | Current time of day (IST) | No new intraday triggers after 14:45 |
| `b` | Breakout buffer | Default 0.1% of price |
| `RVOL_D` | Daily relative volume | `V_D,t / SMA(V_D, 50)` |
| `RVOL_τ` | Time-of-day relative volume | `CumVol_today(9:15 → τ) / avg CumVol(9:15 → τ), last 20 sessions` |

### Core formula (any period)

| Parameter | Rule |
|---|---|
| P (pivot) | `(H + L + C) / 3` of the prior period |
| BC | `(H + L) / 2` |
| TC | `2P - BC` |
| Ordering | If `TC < BC`, swap them |
| Width % | `(TC - BC) / P x 100` |
| Narrow CPR | Width % ≤ 20th percentile of Width % over the last 60 periods |

A percentile threshold adapts to each instrument's volatility. A fixed threshold (like 0.25%) is too tight for mid-caps and too loose for NIFTY.

### Long-term investing (weekly bars)

| Parameter | Rule |
|---|---|
| CPR source | Prior month's H, L, C |
| Long | Narrow CPR and `C_W,t > TC x (1 + b)` |
| Short | Narrow CPR and `C_W,t < BC x (1 - b)` |

### Short-term (swing) (daily bars)

| Parameter | Rule |
|---|---|
| CPR source | Prior week's H, L, C |
| Long | Narrow CPR and `C_D,t > TC x (1 + b)` and `RVOL_D ≥ 1.2` |
| Short | Narrow CPR and `C_D,t < BC x (1 - b)` and `RVOL_D ≥ 1.2` |

### Intraday stock (5-min bars, cash stock)

| Parameter | Rule |
|---|---|
| CPR source | Prior day's H, L, C |
| Long | Narrow CPR and `C_5m,t > TC x (1 + b)` and `RVOL_τ ≥ 1.5`, before 14:45 |
| Short | Narrow CPR and `C_5m,t < BC x (1 - b)` and `RVOL_τ ≥ 1.5`, before 14:45 |
| Context | Tag the open as above / inside / below CPR (changes base rates materially) |

### F&O (continuous front-month futures)

Same rules as intraday stock, run on the continuous front-month futures series (range or levels, trigger bar and volume all from futures). Only the differences:

| Difference | Rule |
|---|---|
| Rollover day | Build CPR from the new contract's own prior-day H, L, C |

---

## 4. 52-Week High / All-Time High (ATH) Breakout

**What it is.** Price closes at its highest level in a year, or ever.

**Why it helps.** There is no overhead supply from trapped buyers above an ATH. Momentum research across markets, including India, shows new highs tend to be followed by further strength more often than chance.

**Fires / invalidates.** Fires on a bar *close* above the level, once per new high (re-arms only after a close back below it). Invalid on a close more than 3% below the broken level, which allows a normal retest.

**Base-rate success.** Price reaches trigger + 1R before invalidation (R = trigger to invalidation distance). Horizon: same session (intraday, F&O), 10 sessions (swing), 13 weeks (long-term).

**Worked example (BEL, swing, long)**

| Item | Value |
|---|---|
| Prior 52-week high | ₹430.00 |
| Trigger (daily close, RVOL_D 1.8) | ₹433.50 (above ₹430.00 x 1.001 = ₹430.43) |
| Invalidation (3% below broken level) | ₹417.10 |
| R = trigger - invalidation | ₹16.40 |
| Success target = trigger + 1R | ₹449.90 |

Price reaches ₹449.90 before ₹417.10 within 10 sessions: success. Price hits ₹417.10 first: failure.

**Data rule.** Use split/bonus-adjusted prices. Unadjusted series turn every corporate action into a fake 52-week or all-time high.

**Terms used**

| Term | Meaning | Formula / default |
|---|---|---|
| `H`, `C`, `V` | High, close, volume of a bar | |
| `_W`, `_D`, `_5m` | Weekly, daily, 5-minute bar | |
| `t` | Current bar | |
| `τ` | Current time of day (IST) | No new intraday triggers after 14:45 |
| `b` | Breakout buffer | Default 0.1% of price |
| `SMA(x, n)` | Simple moving average of x over n bars | |
| `RVOL_D` | Daily relative volume | `V_D,t / SMA(V_D, 50)` |
| `RVOL_W` | Weekly relative volume | `V_W,t / SMA(V_W, 20)` |
| `RVOL_τ` | Time-of-day relative volume | `CumVol_today(9:15 → τ) / avg CumVol(9:15 → τ), last 20 sessions` |

### Core formula

| Parameter | Rule |
|---|---|
| 52WH | `max(H_D)` over the previous 252 sessions (excludes today) |
| ATH | `max(H_D)` over all history before today |

### Long-term investing (weekly bars)

| Parameter | Rule |
|---|---|
| Long | `C_W,t > 52WH x (1 + b)` and `RVOL_W ≥ 1.5` and `C_W,t > SMA(C_D, 200)` |
| ATH mode | `C_W,t > ATH x (1 + b)` and `RVOL_W ≥ 1.5` |
| Pre-alert | `C_W,t ≥ 0.97 x 52WH` ("approaching", informational only) |

### Short-term (swing) (daily bars)

| Parameter | Rule |
|---|---|
| Long | `C_D,t > 52WH x (1 + b)` and `RVOL_D ≥ 1.5` |
| ATH mode | `C_D,t > ATH x (1 + b)` and `RVOL_D ≥ 1.5` |
| Context | Days since the last 52WH (a first new high after a long base behaves differently from the 10th consecutive new high) |

### Intraday stock (5-min bars, cash stock)

| Parameter | Rule |
|---|---|
| Long | `C_5m,t > 52WH x (1 + b)` and `RVOL_τ ≥ 2.0`, before 14:45 |

Intraday 52-week breaks are often news-driven, hence the higher RVOL bar.

### F&O (continuous front-month futures)

Same rules as intraday stock, run on the continuous front-month futures series (range or levels, trigger bar and volume all from futures). Only the differences:

| Difference | Rule |
|---|---|
| 52WH source | Back-adjusted continuous futures series (removes roll jumps between monthly contracts) |
| Index | Same rule; valid but rare |

---

## 5. Base Breakout (Consolidation Near Highs)

**What it is.** A stock trades in a tight sideways range close to its highs for weeks, then breaks out on volume. It captures the core idea of the VCP (Volatility Contraction Pattern) using fixed, measurable rules instead of judging the pattern by eye.

**Why it helps.** Tight consolidation near highs signals sellers are exhausted while holders refuse to sell. The breakout from that coil tends to be sharp. A fixed rule avoids the unreliability of pattern detection.

**Fires / invalidates.** Fires on a bar *close* above the base high, once per base. Invalid on a close below the base low (conservative) or base midpoint (tight).

**Base-rate success.** Price reaches trigger + 1R before invalidation (R = trigger to invalidation distance). Horizon: same session (intraday), 10 sessions (swing), 13 weeks (long-term).

**Worked example (POLYCAB, swing, long)**

| Item | Value |
|---|---|
| Base (last 20 days) | High ₹7,120, low ₹6,640 |
| Depth = (BH - BL) / BH | 480 / 7,120 = 6.7% (≤ 10%) |
| Proximity to 52-week high (₹7,300) | ₹7,120 ≥ 0.95 x ₹7,300 = ₹6,935 |
| Trigger (daily close, RVOL_D 1.6) | ₹7,140 (above ₹7,120 x 1.001 = ₹7,127) |
| Invalidation (base low) | ₹6,640 |
| R = trigger - invalidation | ₹500 |
| Success target = trigger + 1R | ₹7,640 |

Price reaches ₹7,640 before ₹6,640 within 10 sessions: success. Price hits ₹6,640 first: failure.

**Data rule.** Use split/bonus-adjusted prices, otherwise corporate actions distort base depth and the 52-week reference.

**Terms used**

| Term | Meaning | Formula / default |
|---|---|---|
| `H`, `L`, `C`, `V` | High, low, close, volume of a bar | |
| `t` | Current bar | |
| `τ` | Current time of day (IST) | No new intraday triggers after 14:45 |
| `b` | Breakout buffer | Default 0.1% of price |
| `SMA(x, n)` | Simple moving average of x over n bars | |
| `52WH` | 52-week high | Highest daily high of the previous 252 sessions |
| `DATR%` | Daily ATR as a % of yesterday's close | `DATR / C_D,t-1 x 100` |
| `RVOL_D` | Daily relative volume | `V_D,t / SMA(V_D, 50)` |
| `RVOL_W` | Weekly relative volume | `V_W,t / SMA(V_W, 20)` |
| `RVOL_τ` | Time-of-day relative volume | `CumVol_today(9:15 → τ) / avg CumVol(9:15 → τ), last 20 sessions` |

### Core formula

| Parameter | Rule |
|---|---|
| L | Base length in bars |
| BH (base high) | `max(H)` over the previous L bars |
| BL (base low) | `min(L)` over the previous L bars |
| Depth | `(BH - BL) / BH x 100` |
| Proximity | `BH ≥ (1 - p) x 52WH` (base sits near the 52-week high) |
| Dry-up | `SMA(V, 10) / SMA(V, 50) < 0.8` during the base (volume contraction) |
| Trend | `C > SMA(C, 50) > SMA(C, 200)` (stock already in an uptrend) |
| Trigger | `C_t > BH x (1 + b)` and `RVOL ≥ 1.5` (RVOL_D daily, RVOL_W weekly) |

### Long-term investing (weekly bars)

| Parameter | Rule |
|---|---|
| Base length | L = 10 to 26 weeks |
| Depth | ≤ 25% |
| Proximity | p = 10% |
| Trigger | Weekly close, `RVOL_W ≥ 1.5` |

### Short-term (swing) (daily bars)

| Parameter | Rule |
|---|---|
| Base length | L = 20 days (default; range 15 to 40) |
| Depth | ≤ 10% |
| Proximity | p = 5% |
| Trigger | Daily close, `RVOL_D ≥ 1.5` |

### Intraday stock (5-min bars, cash stock)
Midday range-breakout variant (optional):

| Parameter | Rule |
|---|---|
| Base | 5m bars from 11:00 onward, with L ≥ 12 (one hour) |
| Depth | `≤ 0.4 x DATR%` |
| Trigger | `C_5m,t > BH x (1 + b)` and `RVOL_τ ≥ 1.5`, before 14:45 |

### F&O (continuous front-month futures)

Same rules as swing, run on daily bars of the back-adjusted continuous futures series (stock futures only). Not a default preset for indices, where bases are rarely meaningful.

---

## 6. NR7 / Inside Bar Breakout

**What it is.** NR7 is the narrowest range of the last 7 bars. An inside bar sits entirely within the previous bar's range. Both mark volatility compression. The breakout is the first close beyond the compressed bar's high or low.

**Why it helps.** Volatility tends to expand after contracting. The compressed bar gives a clear, tight level with a small risk distance. NR7 plus inside bar (NR7ID) is the strongest combination.

**Fires / invalidates.** Fires on a bar *close* beyond the setup bar's high or low, within 2 bars of the setup; the setup expires otherwise. Invalid at the opposite extreme of the setup bar.

**Base-rate success.** Price reaches trigger + 1R before invalidation (R = trigger to invalidation distance). Horizon: same session (intraday, F&O), 10 sessions (swing), 13 weeks (long-term).

**Worked example (SBIN, intraday on a prior-day NR7, long)**

| Item | Value |
|---|---|
| Yesterday (NR7 day) | High ₹812.40, low ₹806.90 (narrowest range of 7 days) |
| Trigger (5m close today) | ₹813.60 (above ₹812.40 x 1.001 = ₹813.21) |
| Invalidation (NR7 day low) | ₹806.90 |
| R = trigger - invalidation | ₹6.70 |
| Success target = trigger + 1R | ₹820.30 |

Price reaches ₹820.30 before ₹806.90 in the session: success. Price hits ₹806.90 first: failure.

**Terms used**

| Term | Meaning | Formula / default |
|---|---|---|
| `H`, `L`, `C`, `V` | High, low, close, volume of a bar | |
| `Range` | How far price moved within a bar | `H - L` |
| `t` | The setup bar: the compressed bar being tested (e.g. yesterday, on daily bars) | |
| `t-1`, `t-2` … `t-6` | The 1, 2 … 6 bars before the setup bar | |
| `t+1`, `t+2` | The 1st and 2nd bars after the setup bar, where the breakout must happen | |
| `_D`, `_5m` | Daily bar, 5-minute bar | |
| `τ` | Current time of day (IST) | No new intraday triggers after 14:45 |
| `b` | Breakout buffer, so a close just a paisa beyond the level doesn't count | Default 0.1% of price |
| `RVOL_D` | Daily relative volume: today's volume vs normal | `V_D,t / SMA(V_D, 50)` |

### Core formula

| Step | Rule | In plain words |
|---|---|---|
| 1. Measure the bar | `Range_t = H_t - L_t` | Size of the setup bar |
| 2. NR7 test | `Range_t = min(Range_t-6 … Range_t)` | Setup bar is the narrowest of the last 7 bars (itself plus the 6 before it) |
| 3. Inside bar test | `H_t < H_t-1` and `L_t > L_t-1` | Setup bar sits entirely within the previous bar |
| 4. Setup type | NR7, Inside bar, or NR7ID (both tests pass) | NR7ID is the strongest squeeze |
| 5. Levels | Breakout high = `H_t`, breakout low = `L_t` | The setup bar's own high and low |
| 6. Long trigger | On bar t+1 or t+2: `C > H_t x (1 + b)` | A close above the setup bar's high |
| 7. Short trigger | On bar t+1 or t+2: `C < L_t x (1 - b)` | A close below the setup bar's low |
| 8. Expiry | No trigger by the close of t+2 | Setup is cancelled |
| 9. Invalidation | Long: `L_t`. Short: `H_t` | Opposite side of the setup bar |

### Long-term investing (weekly bars)

| Parameter | Rule |
|---|---|
| Setup | Weekly NR7 / inside week |
| Trigger | Weekly close within the next 2 weeks |

### Short-term (swing) (daily bars)

| Parameter | Rule |
|---|---|
| Setup | Daily NR7 / inside bar (primary use) |
| Trigger | Daily close within the next 2 sessions, `RVOL_D ≥ 1.2` |

### Intraday stock (5-min bars, cash stock)

| Parameter | Rule |
|---|---|
| Setup | Yesterday was NR7 (or NR7ID) on daily bars |
| Levels | `H_D,t-1` and `L_D,t-1` |
| Trigger | Today, `C_5m,t > H_D,t-1 x (1 + b)` or `C_5m,t < L_D,t-1 x (1 - b)`, before 14:45 |
| Variant | 15m inside bar within the session (noisier; not a default preset) |

### F&O (continuous front-month futures)

Same rules as intraday stock, run on the continuous front-month futures series (range or levels, trigger bar and volume all from futures). Only the differences:

| Difference | Rule |
|---|---|
| Rollover day | Use the new contract's own prior-day bar for the NR7 setup |
| Alert context | Compression days often coincide with cheap ATM straddles; show straddle premium on the alert (informational only) |

---

## 7. Gap-and-Go (Unfilled Gap Breakout)

**What it is.** Price opens beyond the prior period's range and does not fill the gap. The gap itself is the breakout; holding it confirms it.

**Why it helps.** A gap that holds past the opening shows overnight demand or supply was real, not just an opening imbalance. Gaps that fill are the opposite trade (mean reversion) and are excluded here.

**Fires / invalidates.** Fires only after the gap has held for the confirmation window (below), on a bar *close*. Invalid if price trades back to the prior close (gap filled).

**Base-rate success.** Price reaches trigger + 1R before invalidation (R = trigger to invalidation distance). Horizon: same session (intraday, F&O), 10 sessions (swing).

**Worked example (INFY, intraday, gap up)**

| Item | Value |
|---|---|
| Prior close | ₹1,480.00 |
| Today's open | ₹1,508.00 (gap +1.9%) |
| 9:15 to 9:45 range | High ₹1,516.00, low ₹1,495.00 (gap held above ₹1,480) |
| Trigger (5m close) | ₹1,518.20 (above ₹1,516.00 x 1.001 = ₹1,517.52) |
| Invalidation (gap filled = prior close) | ₹1,480.00 |
| R = trigger - invalidation | ₹38.20 |
| Success target = trigger + 1R | ₹1,556.40 |

Price reaches ₹1,556.40 before ₹1,480.00 in the session: success. Price hits ₹1,480.00 first: failure.

**Terms used**

| Term | Meaning | Formula / default |
|---|---|---|
| `O`, `H`, `L`, `C`, `V` | Open, high, low, close, volume of a bar | |
| `t` | Today | |
| `t-1` | Previous session | |
| `_D`, `_5m` | Daily, 5-minute bar | |
| `τ` | Current time of day (IST) | No new intraday triggers after 14:45 |
| `b` | Breakout buffer | Default 0.1% of price |
| `ATR(14)` | Average true range | 14 bars of the timeframe in use |
| `DATR` | Daily ATR, in price units (₹ or index points) | `ATR(14)` on daily bars |
| `DATR%` | Daily ATR as a % of yesterday's close | `DATR / C_D,t-1 x 100` |
| `RVOL_D` | Daily relative volume | `V_D,t / SMA(V_D, 50)` |
| `RVOL_τ` | Time-of-day relative volume | `CumVol_today(9:15 → τ) / avg CumVol(9:15 → τ), last 20 sessions` |

### Core formula

| Parameter | Rule |
|---|---|
| Gap % | `(O_t - C_t-1) / C_t-1 x 100` |
| Full gap up | `O_t > H_t-1` (clears the whole prior range) |
| Size filter | `abs(O_t - C_t-1) ≥ 0.5 x ATR(14)` |

### Long-term investing
Not a default preset. Weekly breakaway gaps are rare and usually event-driven; better handled by the 52-week / base breakout agents.

### Short-term (swing) (daily bars)
Breakaway gap:

| Parameter | Rule |
|---|---|
| Setup | `O_D,t > H_D,t-1` and `abs(O_D,t - C_D,t-1) ≥ 0.5 x DATR` and `RVOL_D ≥ 2.0` |
| Confirm | `min(L_D,t to L_D,t+2) > H_D,t-1` (gap unfilled for 3 sessions) |
| Fires | On the close of day t+2 |

### Intraday stock (5-min bars, cash stock)

| Parameter | Rule |
|---|---|
| Setup | `Gap % ≥ g`, default `g = max(1%, 0.5 x DATR%)` |
| Hold | Lowest low from 9:15 to 9:45 stays above `C_D,t-1` (gap not filled in the first 30 min) |
| Trigger | `C_5m,t > H_30 x (1 + b)` and `RVOL_τ ≥ 2.0`, before 14:45, where H_30 = highest high from 9:15 to 9:45 |
| Short | Mirror for gap down |

Operationally this is a gap filter on top of a 30-minute ORB.

### F&O (continuous front-month futures)

Same rules as intraday stock, run on the continuous front-month futures series (range or levels, trigger bar and volume all from futures). Only the differences:

| Difference | Rule |
|---|---|
| Gap measured on | Futures open vs futures prior close |
| Rollover day | Measure against the new contract's own prior close; the stitched series shows a false gap equal to the spread between contracts |

---

## Summary: Which Breakout Serves Which Segment

| Breakout | Long-term (weekly) | Swing (daily) | Intraday stock (5-min) | F&O (5-min, futures) |
|---|---|---|---|---|
| ORB | ✗ | ✗ | ✓ Default | ✓ Default |
| Previous High / Previous Low (D / W / M) | ✓ Prior month | ✓ Prior week | ✓ Default | ✓ Default |
| CPR | ✓ Monthly CPR | ✓ Weekly CPR | ✓ Daily CPR | ✓ Daily CPR (futures) |
| 52-week / ATH | ✓ Default | ✓ Default | ✓ High RVOL only | ✓ Stock futures |
| Base breakout | ✓ Weekly | ✓ Default | Optional (midday variant) | Stock futures (daily) |
| NR7 / Inside bar | ✓ Weekly | ✓ Default | ✓ Prior-day NR7 | ✓ Prior-day NR7 |
| Gap-and-go | ✗ | ✓ Breakaway gap | ✓ Default | ✓ Default |

All defaults (b, RVOL thresholds, widths, lookbacks) are starting parameters. Each agent should expose them in the custom builder and show the base-rate card for the default and its nearest variants.
