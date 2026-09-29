"""
Breakout library engine — implements breakout_library.md for Daily / Weekly /
Monthly bars (intraday parts of the library are out of scope for now).

Six detectors run here (all fire on a bar CLOSE beyond a level, never a touch):

    PREV_HL  Previous High / Previous Low     levels PWH/PWL (daily), PMH/PML (weekly, monthly)
    CPR      CPR Breakout                     levels TC / BC (P shown for context)
    HIGH52   52-Week High / ATH Breakout      levels 52WH / ATH
    BASE     Base Breakout                    levels BH / BL (consolidation near highs)
    NR7      NR7 / Inside Bar Breakout        setup NR7 / Inside / NR7ID
    GAP      Gap-and-Go (Unfilled Gap)        daily only

ORB is purely intraday (the library marks it "not applicable" for daily/weekly), so
it has no D/W/M form. Gap-and-Go is marked "not a default preset" for weekly, so it
runs on daily only.

Every event carries the library's trade card: trigger (the closing price), the
invalidation level, R = |trigger - invalidation| and the success target = trigger
+/- 1R. Parameters live in config.yaml (`breakouts:`), never hard-coded here.

Where the library is silent for a timeframe (e.g. CPR / 52WH / NR7 on MONTHLY bars)
the weekly rule is reused on monthly bars — those events are tagged `extrapolated`.
"""

import math

from atr import atr
from resample import to_weekly, to_monthly
from settings import CFG
from datetime import datetime, timedelta

BC = CFG["breakouts"]
B = BC["buffer"]                      # b: a close must clear the level by this fraction
TFS = ("1d", "1w", "1m")

NAMES = {
    "PREV_HL": "Previous High / Low",
    "CPR": "CPR Breakout",
    "HIGH52": "52-Week High / ATH",
    "BASE": "Base Breakout",
    "NR7": "NR7 / Inside Bar",
    "GAP": "Gap-and-Go",
}


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _mean(xs):
    return sum(xs) / len(xs) if xs else None


def _rvol(V, t, n):
    """Relative volume: this bar's volume / mean volume of the n bars BEFORE it."""
    base = [x for x in V[max(0, t - n):t] if x]
    if len(base) < max(3, n // 2):
        return None
    m = _mean(base)
    return V[t] / m if m else None


def _dt(s):
    return datetime.strptime(s[:10], "%Y-%m-%d")


class _Ctx:
    """Everything one (symbol, timeframe) scan needs, computed once."""

    def __init__(self, tf, rows, daily):
        self.tf, self.rows = tf, rows
        self.n = len(rows)
        self.d = [r[0][:10] for r in rows]
        self.o = [r[1] for r in rows]
        self.h = [r[2] for r in rows]
        self.l = [r[3] for r in rows]
        self.c = [r[4] for r in rows]
        self.v = [r[5] or 0 for r in rows]
        self.daily = daily

        # Is the newest bar still forming? (weekly/monthly bars built from the days so
        # far). Approximate calendar test — conservative, fixes itself next session.
        last = _dt(self.d[-1])
        self.forming_last = False
        if tf == "1w":
            self.forming_last = last.weekday() < 4                      # before Friday
        elif tf == "1m":
            nxt = (last.replace(day=28) + timedelta(days=4)).replace(day=1)
            self.forming_last = (nxt - last).days > 4                   # >4 days to month-end

        # Period grid for previous-period levels / CPR: daily bars look at the prior
        # WEEK; weekly and monthly bars look at the prior MONTH.
        if tf == "1d":
            self.prows = to_weekly(daily)
            self.pkey = lambda date: _dt(date).isocalendar()[:2]
        else:
            self.prows = to_monthly(daily)
            self.pkey = lambda date: date[:7]
        self.pidx = {}
        seen = {}
        for r in daily:
            k = self.pkey(r[0])
            if k not in seen:
                seen[k] = len(seen)
        self.pidx = seen
        self._sma = None

    # -- period helpers ------------------------------------------------------
    def pi(self, t):
        return self.pidx.get(self.pkey(self.d[t]))

    def prev_period(self, t):
        """(H, L, C) of the period before bar t's period, or None."""
        k = self.pi(t)
        if k is None or k < 1:
            return None
        p = self.prows[k - 1]
        return p[2], p[3], p[4]

    def period_start(self, t):
        """Date of the first bar of bar t's period (where a level line starts)."""
        k = self.pi(t)
        s = t
        while s > 0 and self.pi(s - 1) == k:
            s -= 1
        return self.d[s]

    # -- daily SMAs (50 / 200 of DAILY closes) looked up by bar date -----------
    def sma(self, t, n):
        if self._sma is None:
            cl = [r[4] for r in self.daily]
            pre = [0.0]
            for x in cl:
                pre.append(pre[-1] + x)
            self._sma = ({r[0][:10]: i for i, r in enumerate(self.daily)}, pre)
        idx, pre = self._sma
        i = idx.get(self.d[t])
        if i is None or i + 1 < n:
            return None
        return (pre[i + 1] - pre[i + 1 - n]) / n

    def fire(self, t):
        return t - 1 >= 0


def _event(x, code, level_name, direction, t, level, trigger, inval, lines,
           variant=None, ctx="", rvol=None, extrapolated=False):
    """Assemble the library's trade card. Returns None if the risk is degenerate."""
    long_ = direction == "Long"
    R = (trigger - inval) if long_ else (inval - trigger)
    if R <= 0:
        return None
    target = trigger + R if long_ else trigger - R
    return {
        "type": NAMES[code], "code": code, "level_name": level_name,
        "variant": variant, "direction": direction, "timeframe": x.tf,
        "level": round(level, 2), "trigger": round(trigger, 2),
        "invalidation": round(inval, 2), "r": round(R, 2),
        "r_pct": round(R / trigger * 100, 2), "target": round(target, 2),
        "rvol": round(rvol, 2) if rvol is not None else None,
        "trigger_date": x.d[t], "bars_ago": x.n - 1 - t,
        "forming": bool(t == x.n - 1 and x.forming_last),
        "extrapolated": extrapolated, "context": ctx, "lines": lines,
    }


def _hline(label, price, d_from, d_to, style="solid"):
    return {"label": label, "price": round(price, 2), "from": d_from, "to": d_to, "style": style}


def _rv_n(tf):
    return BC["rvol_bars"][tf]


# ---------------------------------------------------------------------------
# 2. Previous High / Previous Low
# ---------------------------------------------------------------------------
def det_prev_hl(x, t):
    pp = x.prev_period(t)
    if not pp or t < 1:
        return []
    PH, PL, _ = pp
    names = ("PWH", "PWL") if x.tf == "1d" else ("PMH", "PML")
    rv = _rvol(x.v, t, _rv_n(x.tf))
    cfg = BC["prev_hl"][x.tf]                       # {long_rvol, short_rvol} (null = none)
    start = x.period_start(t)
    out = []

    up = PH * (1 + B)
    if x.c[t] > up and x.c[t - 1] <= up and _rv_ok(rv, cfg["long_rvol"]):
        ev = _event(x, "PREV_HL", names[0], "Long", t, PH, x.c[t], x.l[t],
                    [_hline(names[0], PH, start, x.d[t])], rvol=rv,
                    extrapolated=x.tf == "1m",
                    ctx=f"closed above previous {'week' if x.tf == '1d' else 'month'} high")
        if ev:
            out.append(ev)
    dn = PL * (1 - B)
    if x.c[t] < dn and x.c[t - 1] >= dn and _rv_ok(rv, cfg["short_rvol"]):
        ev = _event(x, "PREV_HL", names[1], "Short", t, PL, x.c[t], x.h[t],
                    [_hline(names[1], PL, start, x.d[t])], rvol=rv,
                    extrapolated=x.tf == "1m",
                    ctx=f"closed below previous {'week' if x.tf == '1d' else 'month'} low")
        if ev:
            out.append(ev)
    return out


def _rv_ok(rv, need):
    """RVOL requirement: None = no requirement; else RVOL must exist and clear it."""
    if need is None:
        return True
    return rv is not None and rv >= need


# ---------------------------------------------------------------------------
# 3. CPR Breakout
# ---------------------------------------------------------------------------
def _cpr(H, L, C):
    P = (H + L + C) / 3
    bc = (H + L) / 2
    tc = 2 * P - bc
    if tc < bc:
        tc, bc = bc, tc
    return P, bc, tc, (tc - bc) / P * 100


def det_cpr(x, t):
    pp = x.prev_period(t)
    k = x.pi(t)
    if not pp or t < 1 or k is None:
        return []
    P, bc, tc, width = _cpr(*pp)

    # Narrow = width <= Nth percentile of the last `window` periods' widths.
    cfg = BC["cpr"]
    lo = max(1, k - cfg["window"] + 1)
    widths = []
    for j in range(lo, k + 1):
        p = x.prows[j - 1]
        widths.append(_cpr(p[2], p[3], p[4])[3])
    if len(widths) < cfg["min_periods"]:
        return []
    ws = sorted(widths)
    thr = ws[max(0, math.ceil(cfg["percentile"] / 100 * len(ws)) - 1)]
    if width > thr:
        return []

    rv = _rvol(x.v, t, _rv_n(x.tf))
    need = cfg["rvol"][x.tf]
    start = x.period_start(t)
    lines = [_hline("TC", tc, start, x.d[t]), _hline("BC", bc, start, x.d[t]),
             _hline("P", P, start, x.d[t], "dotted")]
    ctx = f"narrow CPR ({width:.2f}% wide)"
    out = []
    up = tc * (1 + B)
    if x.c[t] > up and x.c[t - 1] <= up and _rv_ok(rv, need):
        ev = _event(x, "CPR", "TC", "Long", t, tc, x.c[t], bc, lines, rvol=rv,
                    ctx=ctx, extrapolated=x.tf == "1m")
        if ev:
            out.append(ev)
    dn = bc * (1 - B)
    if x.c[t] < dn and x.c[t - 1] >= dn and _rv_ok(rv, need):
        ev = _event(x, "CPR", "BC", "Short", t, bc, x.c[t], tc, lines, rvol=rv,
                    ctx=ctx, extrapolated=x.tf == "1m")
        if ev:
            out.append(ev)
    return out


# ---------------------------------------------------------------------------
# 4. 52-Week High / All-Time High
# ---------------------------------------------------------------------------
def det_high52(x, t):
    n52 = BC["high52"]["bars"][x.tf]
    if t < n52 or t < 1:
        return []
    W = max(x.h[t - n52:t])
    ATH = max(x.h[:t])
    rv = _rv_ok_val = _rvol(x.v, t, _rv_n(x.tf))
    need = BC["high52"]["rvol"]
    if not _rv_ok(rv, need):
        return []

    ath_up = ATH * (1 + B)
    w_up = W * (1 + B)
    if x.c[t] > ath_up and x.c[t - 1] <= ath_up:
        name, level, var = "ATH", ATH, "ATH"
    elif x.c[t] > w_up and x.c[t - 1] <= w_up:
        # Weekly/monthly 52WH also require the daily close above its 200-day SMA.
        if x.tf != "1d":
            s200 = x.sma(t, 200)
            if s200 is None or x.c[t] <= s200:
                return []
        name, level, var = "52WH", W, "52WH"
    else:
        return []

    # Context: bars since the previous close that broke its own trailing 52-bar high.
    since = None
    for j in range(t - 1, n52, -1):
        if x.c[j] > max(x.h[j - n52:j]):
            since = t - j
            break
    ctx = ("first new high in over a year" if since is None
           else f"previous new high {since} bars ago")
    if var == "ATH":
        ctx += f" · ATH measured on stored history (since {x.d[0][:4]})"
    return [e for e in [_event(
        x, "HIGH52", name, "Long", t, level, x.c[t], level * (1 - BC["high52"]["invalid_pct"] / 100),
        [_hline(name, level, x.d[max(0, t - n52)], x.d[t])],
        variant=var, ctx=ctx, rvol=rv, extrapolated=x.tf == "1m")] if e]


# ---------------------------------------------------------------------------
# 5. Base Breakout
# ---------------------------------------------------------------------------
def det_base(x, t):
    cfg = BC["base"][x.tf]
    n52 = BC["high52"]["bars"][x.tf]
    sh, lg = cfg["dryup_bars"]
    if t < max(n52, lg, max(cfg["lengths"])) + 1:
        return []
    rv = _rvol(x.v, t, _rv_n(x.tf))
    if not _rv_ok(rv, cfg["rvol"]):
        return []
    W = max(x.h[t - n52:t])
    s50, s200 = x.sma(t, 50), x.sma(t, 200)
    if s50 is None or s200 is None or not (x.c[t] > s50 > s200):
        return []                                                     # trend filter
    v_short = _mean(x.v[t - sh:t])
    v_long = _mean(x.v[t - lg:t])
    dry = (v_short / v_long) if v_long else None
    if dry is None or dry >= BC["base"]["dryup_max"]:
        return []                                                     # volume dry-up

    for L in sorted(cfg["lengths"], reverse=True):                    # prefer the longest valid base
        BH = max(x.h[t - L:t])
        BL = min(x.l[t - L:t])
        depth = (BH - BL) / BH * 100
        if depth > cfg["depth_pct"] or BH < (1 - cfg["prox_pct"] / 100) * W:
            continue
        up = BH * (1 + B)
        if not (x.c[t] > up and x.c[t - 1] <= up):
            continue
        d0 = x.d[t - L]
        ev = _event(x, "BASE", "BH", "Long", t, BH, x.c[t], BL,
                    [_hline("BH", BH, d0, x.d[t]), _hline("BL", BL, d0, x.d[t])],
                    variant=f"{L}-bar base", rvol=rv, extrapolated=x.tf == "1m",
                    ctx=f"{L}-bar base, depth {depth:.1f}%, vol dry-up {dry:.2f}, "
                        f"{(1 - BH / W) * 100:.1f}% below 52WH")
        if ev:
            return [ev]
    return []


# ---------------------------------------------------------------------------
# 6. NR7 / Inside Bar
# ---------------------------------------------------------------------------
def _setup_type(x, s):
    """NR7 / Inside / NR7ID for the setup bar s, or None."""
    if s < 6:
        return None
    rng = [x.h[i] - x.l[i] for i in range(s - 6, s + 1)]
    nr7 = rng[-1] == min(rng)
    inside = x.h[s] < x.h[s - 1] and x.l[s] > x.l[s - 1]
    if nr7 and inside:
        return "NR7ID"
    return "NR7" if nr7 else ("Inside" if inside else None)


def det_nr7(x, t):
    out = []
    rv = _rvol(x.v, t, _rv_n(x.tf))
    need = BC["nr7"]["rvol"][x.tf]
    for s in (t - 1, t - 2):                 # trigger must come within 2 bars of the setup
        if s < 6:
            continue
        typ = _setup_type(x, s)
        if not typ:
            continue
        H, L = x.h[s], x.l[s]
        up, dn = H * (1 + B), L * (1 - B)
        if s == t - 2 and not (dn <= x.c[t - 1] <= up):
            continue                          # already triggered (or broke) on t-1
        lines = [_hline("Setup high", H, x.d[s], x.d[t]), _hline("Setup low", L, x.d[s], x.d[t])]
        if x.c[t] > up and _rv_ok(rv, need):
            ev = _event(x, "NR7", "Setup high", "Long", t, H, x.c[t], L, lines, variant=typ,
                        rvol=rv, ctx=f"{typ} bar on {x.d[s]}", extrapolated=x.tf == "1m")
        elif x.c[t] < dn and _rv_ok(rv, need):
            ev = _event(x, "NR7", "Setup low", "Short", t, L, x.c[t], H, lines, variant=typ,
                        rvol=rv, ctx=f"{typ} bar on {x.d[s]}", extrapolated=x.tf == "1m")
        else:
            continue
        if ev:
            out.append(ev)
            break                              # one event per trigger bar (prefer the nearer setup)
    return out


# ---------------------------------------------------------------------------
# 7. Gap-and-Go (daily)
# ---------------------------------------------------------------------------
def det_gap(x, t):
    if x.tf != "1d":
        return []
    g = t - 2                                  # gap day; fires on the close of day g+2
    if g < 15:
        return []
    cfg = BC["gap"]
    rv = _rvol(x.v, g, _rv_n("1d"))
    if not _rv_ok(rv, cfg["rvol"]):
        return []
    a = atr(x.rows[:g], 14)                    # ATR(14) as of the prior close
    pc = x.c[g - 1]
    if not a or abs(x.o[g] - pc) < cfg["size_atr"] * a:
        return []
    gap_pct = (x.o[g] - pc) / pc * 100
    start = x.d[g - 1]
    ctx = f"gap {gap_pct:+.1f}% on {x.d[g]}, unfilled 3 sessions"
    if x.o[g] > x.h[g - 1] and min(x.l[g:t + 1]) > x.h[g - 1]:
        ev = _event(x, "GAP", "Gap edge (prior high)", "Long", t, x.h[g - 1], x.c[t], pc,
                    [_hline("Prior high", x.h[g - 1], start, x.d[t]),
                     _hline("Prior close", pc, start, x.d[t], "dotted")],
                    rvol=rv, ctx=ctx)
        return [ev] if ev else []
    if x.o[g] < x.l[g - 1] and max(x.h[g:t + 1]) < x.l[g - 1]:
        ev = _event(x, "GAP", "Gap edge (prior low)", "Short", t, x.l[g - 1], x.c[t], pc,
                    [_hline("Prior low", x.l[g - 1], start, x.d[t]),
                     _hline("Prior close", pc, start, x.d[t], "dotted")],
                    rvol=rv, ctx=ctx)
        return [ev] if ev else []
    return []


DETECTORS = [det_prev_hl, det_cpr, det_high52, det_base, det_nr7, det_gap]


# ---------------------------------------------------------------------------
# driver
# ---------------------------------------------------------------------------
def scan_symbol(symbol, daily, turnover=None):
    """All breakout events that fired within the freshness window, all timeframes."""
    out = []
    for tf in TFS:
        rows = daily if tf == "1d" else (to_weekly(daily) if tf == "1w" else to_monthly(daily))
        if len(rows) < 30:
            continue
        x = _Ctx(tf, rows, daily)
        for t in range(max(1, x.n - BC["fresh_bars"][tf]), x.n):
            for det in DETECTORS:
                for ev in det(x, t):
                    ev["symbol"] = symbol
                    ev["close"] = round(x.c[-1], 2)
                    ev["turnover_cr"] = round(turnover, 2) if turnover is not None else None
                    out.append(ev)
    return out


def scan_all(symbol_to_rows):
    """Run every detector over every liquid symbol. Newest fires first, then RVOL."""
    from screener import _turnover_cr
    rel = CFG.get("reliability", {})
    min_t = rel.get("min_turnover_cr", 0.0)
    lb = rel.get("turnover_lookback", 20)
    out = []
    for symbol, daily in symbol_to_rows.items():
        turnover = _turnover_cr(daily, lb)
        if min_t and (turnover is None or turnover < min_t):
            continue
        out.extend(scan_symbol(symbol, daily, turnover))
    out.sort(key=lambda e: (e["bars_ago"], -(e["rvol"] or 0)))
    return out


if __name__ == "__main__":
    import db
    from collections import Counter
    res = scan_all({s: db.read_candles(s) for s in db.list_symbols()})
    print(len(res), "events")
    for k, v in sorted(Counter((e["code"], e["timeframe"]) for e in res).items()):
        print(f"  {k[0]:8s} {k[1]}: {v}")
