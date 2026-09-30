/* NSE Screener — static frontend. Two tabs share one list + one chart:
     "sr" = Support/Resistance lines  (data/screener.json)
     "bo" = Breakout library          (data/breakouts.json)
   Rows already carry their own geometry, so a click only fetches that stock's candles. */

const LC = LightweightCharts;

const state = {
  mode: "sr", tf: "1d", chartType: "candles", key: null, cand: null, candles: null,
  sr: { filters: { dAtrMax: 0.5, minTouch: 6, minConf: 80, minTurnover: 5, setupType: "All" },
        sort: { col: "confidence", dir: "desc" } },
  bo: { filters: { dir: "All", type: "All", minRvol: 2, minTurnover: 5 },
        sort: { col: "fired", dir: "asc" } },
  xo: { filters: { dir: "Both", ma: "SMA", period: "200", minRvol: 0, minTurnover: 5 },
        sort: { col: "fired", dir: "asc" } },
};
let SR = [], BO = [], XO = [], SUMMARY = null;

// ---- formatting --------------------------------------------------------
const safeName = (s) => s.replace(/[^A-Za-z0-9]/g, "_");            // matches build_site._safe
const inr = (n) => (n == null ? "—" : "₹" + n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
const px = (n) => (n == null ? "—" : n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
const signed = (n) => (n == null ? "—" : (n >= 0 ? "+" : "") + n.toFixed(2));
const xfmt = (n) => (n == null ? "—" : n >= 10 ? Math.round(n) + "×" : n.toFixed(1) + "×");
const MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const dfmt = (s) => { if (!s) return "—"; const [y, m, d] = s.slice(0, 10).split("-"); return `${+d} ${MON[+m - 1]} ${y}`; };
const TF_WORD = { "1d": "daily", "1w": "weekly", "1m": "monthly" };
const TF_BAR = { "1d": "day", "1w": "week", "1m": "month" };
const RVOL_N = { "1d": 50, "1w": 20, "1m": 12 };   // matches config breakouts.rvol_bars
const volSub = (tf) => `vs last 20 ${TF_BAR[tf]}s`;
const sym = (c) => c.symbol.replace("-EQ", "");

// ---- backtest band lookup (S/R) ----------------------------------------
function bandHold(c) {
  if (!SUMMARY || !SUMMARY.cat) return null;
  const cd = SUMMARY.cat[c.setup]; if (!cd) return null;
  const tfd = cd[c.timeframe]; if (!tfd) return null;
  const band = SUMMARY.bands.find(([lab, lo, hi]) => c.confidence >= lo && c.confidence < hi);
  if (!band) return null;
  const v = tfd[band[0]];
  return v && v.n ? { rev: v.rev, move: v.move, n: v.n } : null;
}

// ---- columns -------------------------------------------------------------
const setupPill = (s) => {
  const cls = s.startsWith("Support Rev") ? "up" : s.startsWith("Resistance Rev") ? "down" : "amber";
  return `<span class="pill ${cls}">${s}</span>`;
};
const confBar = (c) => `${Math.round(c)}%<span class="bar"><b style="width:${Math.round(c)}%"></b></span>`;

const COLS = {
  sr: [
    { key: "symbol", label: "Symbol", l: true, html: (c) => `<span class="sym">${sym(c)}</span>`, sort: (c) => c.symbol },
    { key: "close", label: "LTP", html: (c) => px(c.close), sort: (c) => c.close ?? 0 },
    { key: "setup", label: "Setup", l: true, html: (c) => setupPill(c.setup), sort: (c) => c.setup },
    { key: "line_type", label: "Line", l: true, html: (c) => `<span class="dim">${c.line_type === "trendline" ? "trend" : "flat"}</span>`, sort: (c) => c.line_type },
    { key: "touches", label: "Touches", html: (c) => c.touches, sort: (c) => c.touches },
    { key: "confidence", label: "Conf", html: (c) => confBar(c.confidence), sort: (c) => c.confidence },
    { key: "distance_atr", label: "ΔATR", html: (c) => signed(c.distance_atr), sort: (c) => c.distance_atr ?? 0 },
    { key: "vol_ratio", label: "Vol", html: (c) => `<span class="${c.vol_ratio >= 1.5 ? "up" : "dim"}">${xfmt(c.vol_ratio)}</span>`, sort: (c) => c.vol_ratio ?? -1 },
  ],
  bo: [
    { key: "symbol", label: "Symbol", l: true, html: (e) => `<span class="sym">${sym(e)}</span>`, sort: (e) => e.symbol },
    { key: "close", label: "LTP", html: (e) => px(e.close), sort: (e) => e.close },
    { key: "type", label: "Breakout", l: true,
      html: (e) => `${e.type}${e.variant && e.code !== "HIGH52" ? ` <span class="dim">· ${e.variant}</span>` : ""}${e.extrapolated ? ' <span class="dim">*</span>' : ""}`,
      sort: (e) => e.type },
    { key: "direction", label: "Dir", l: true, html: (e) => `<span class="pill ${e.direction === "Long" ? "up" : "down"}">${e.direction}</span>`, sort: (e) => e.direction },
    { key: "trigger", label: "Trigger", html: (e) => px(e.trigger), sort: (e) => e.trigger },
    { key: "r_pct", label: "Risk", html: (e) => e.r_pct.toFixed(1) + "%", sort: (e) => e.r_pct },
    { key: "rvol", label: "Vol surge", html: (e) => `<span class="${e.rvol >= 1.5 ? "up" : "dim"}">${xfmt(e.rvol)}</span>`, sort: (e) => e.rvol ?? -1 },
    { key: "fired", label: "Fired", html: (e) => `<span class="muted">${firedText(e)}</span>`, sort: (e) => e.bars_ago },
  ],
};
COLS.xo = [
  { key: "symbol", label: "Symbol", l: true, html: (e) => `<span class="sym">${sym(e)}</span>`, sort: (e) => e.symbol },
  { key: "close", label: "LTP", html: (e) => px(e.close), sort: (e) => e.close },
  { key: "ma", label: "Average", l: true, html: (e) => `${e.ma_type} ${e.period}`, sort: (e) => e.ma_type + e.period },
  { key: "direction", label: "Cross", l: true, html: (e) => `<span class="pill ${e.direction === "Bullish" ? "up" : "down"}">${e.direction}</span>`, sort: (e) => e.direction },
  { key: "ma_value", label: "MA value", html: (e) => px(e.ma_value), sort: (e) => e.ma_value },
  { key: "dist_pct", label: "vs MA", html: (e) => `<span class="${e.dist_pct >= 0 ? "up" : "down"}">${signed(e.dist_pct)}%</span>`, sort: (e) => e.dist_pct },
  { key: "rvol", label: "Vol surge", html: (e) => `<span class="${e.rvol >= 1.5 ? "up" : "dim"}">${xfmt(e.rvol)}</span>`, sort: (e) => e.rvol ?? -1 },
  { key: "fired", label: "Crossed", html: (e) => `<span class="muted">${firedText(e)}</span>`, sort: (e) => e.bars_ago },
];
const firedText = (e) => (e.forming ? "live" : e.bars_ago === 0 ? "latest bar" : `${e.bars_ago} bar${e.bars_ago > 1 ? "s" : ""} ago`);
const cols = () => COLS[state.mode].filter((c) => c.need !== "summary" || SUMMARY);
const rowKey = (c) => state.mode === "sr"
  ? `${c.symbol}:${c.line_type}:${c.timeframe}:${c.value_now}`
  : state.mode === "bo"
  ? `${c.symbol}:${c.code}:${c.timeframe}:${c.direction}:${c.trigger_date}:${c.level}`
  : `${c.symbol}:${c.ma_type}:${c.period}:${c.timeframe}:${c.cross_date}`;

// ---- filtering / sorting -----------------------------------------------
function passSR(c) {
  const f = state.sr.filters;
  if (Math.abs(c.distance_atr ?? 0) > f.dAtrMax) return false;
  if (c.touches < f.minTouch || c.confidence < f.minConf) return false;
  if ((c.turnover_cr ?? 0) < f.minTurnover) return false;
  if (f.setupType === "Breakouts") return c.setup === "Resistance Breakout" || c.setup === "Support Breakdown";
  if (f.setupType !== "All") return c.setup === f.setupType;
  return true;
}
function passBO(e) {
  const f = state.bo.filters;
  if (f.dir !== "All" && e.direction !== f.dir) return false;
  if (f.type !== "All" && e.code !== f.type) return false;
  if (f.minRvol > 0 && (e.rvol ?? 0) < f.minRvol) return false;
  return (e.turnover_cr ?? 0) >= f.minTurnover;
}
function passXO(e) {
  const f = state.xo.filters;
  if (f.dir !== "Both" && e.direction !== f.dir) return false;
  if (e.ma_type !== f.ma || String(e.period) !== f.period) return false;
  if (f.minRvol > 0 && (e.rvol ?? 0) < f.minRvol) return false;
  return (e.turnover_cr ?? 0) >= f.minTurnover;
}
const PASS = { sr: passSR, bo: passBO, xo: passXO };

function sortRows(rows) {
  const s = state[state.mode].sort;
  const col = COLS[state.mode].find((x) => x.key === s.col) || COLS[state.mode][0];
  const mul = s.dir === "asc" ? 1 : -1;
  return rows.sort((a, b) => {
    const va = col.sort(a), vb = col.sort(b);
    const r = typeof va === "string" ? va.localeCompare(vb) : va - vb;
    return r !== 0 ? mul * r : (b.rvol ?? b.confidence ?? 0) - (a.rvol ?? a.confidence ?? 0);
  });
}

// ---- data load -----------------------------------------------------------
async function loadAll() {
  const [scr, bo, xo, sum] = await Promise.all([
    fetch("data/screener.json").then((r) => r.json()),
    fetch("data/breakouts.json").then((r) => (r.ok ? r.json() : [])).catch(() => []),
    fetch("data/crossovers.json").then((r) => (r.ok ? r.json() : [])).catch(() => []),
    fetch("data/backtest_summary.json").then((r) => (r.ok ? r.json() : null)).catch(() => null),
  ]);
  SR = scr; BO = bo; XO = xo; SUMMARY = sum;
  if (SUMMARY && SUMMARY.page) document.getElementById("bt-link").style.display = "";
  renderFilters();
  loadList();
}
async function loadMeta() {
  try {
    const m = await fetch("data/meta.json").then((r) => r.json());
    if (m.data_through) document.getElementById("generated").textContent = `Last updated: ${dfmt(m.data_through)}`;
  } catch (e) { /* optional */ }
}

// ---- filter bar (per mode) -------------------------------------------------
// Filter chips group by breakout FAMILY (code); the table shows the specific name.
const TYPES = ["All", "PREV_HL", "CPR", "HIGH52", "BASE", "NR7", "GAP"];
const TYPE_SHORT = { PREV_HL: "Prev High/Low", CPR: "CPR", HIGH52: "52W High / ATH", BASE: "Base", NR7: "NR7 / Inside", GAP: "Gap Up / Down" };

const field = (id, label, tip, val, step) =>
  `<label class="field" title="${tip}">${label}<input type="number" id="${id}" value="${val}" step="${step}" min="0"></label>`;
const chips = (id, items, active, short = {}) =>
  `<div class="chips" id="${id}">${items.map((t) => `<button data-v="${t}" class="${t === active ? "active" : ""}">${short[t] || t}</button>`).join("")}</div>`;

function renderFilters() {
  const box = document.getElementById("filters");
  if (state.mode === "sr") {
    const f = state.sr.filters;
    box.innerHTML = `
      <div class="frow">
        ${chips("c-setup", ["All", "Support Reversal", "Resistance Reversal", "Breakouts"], f.setupType,
                { "Support Reversal": "Support bounce", "Resistance Reversal": "Resistance rejection", Breakouts: "Breaks" })}
        <span class="shown" id="shown"></span>
      </div>
      <div class="frow">
        ${field("f-datr", "Max ΔATR", "How close price is to the line, in volatility (ATR) units", f.dAtrMax, 0.1)}
        ${field("f-touch", "Min touches", "How many times price has tested the line", f.minTouch, 1)}
        ${field("f-conf", "Min conf %", "Line-quality score, 0–100", f.minConf, 1)}
        ${field("f-turn", "Min ₹ cr/day", "Average daily traded value, in ₹ crore", f.minTurnover, 1)}
      </div>`;
    bindNum("f-datr", state.sr.filters, "dAtrMax", parseFloat);
    bindNum("f-touch", state.sr.filters, "minTouch", (v) => parseInt(v, 10));
    bindNum("f-conf", state.sr.filters, "minConf", parseFloat);
    bindNum("f-turn", state.sr.filters, "minTurnover", parseFloat);
    bindChips("c-setup", (v) => (state.sr.filters.setupType = v));
  } else if (state.mode === "xo") {
    const f = state.xo.filters;
    box.innerHTML = `
      <div class="frow">
        <div class="field">Direction${chips("c-dir", ["Both", "Bullish", "Bearish"], f.dir)}</div>
        <div class="field">Average${chips("c-ma", ["SMA", "EMA"], f.ma)}</div>
        <div class="field">Period${chips("c-period", ["100", "200", "220"], f.period)}</div>
        <span class="shown" id="shown"></span>
      </div>
      <div class="frow">
        ${field("f-rvol", "Min volume surge", "Volume on the crossing bar vs its normal average", f.minRvol, 0.1)}
        ${field("f-turn", "Min ₹ cr/day", "Average daily traded value, in ₹ crore", f.minTurnover, 1)}
      </div>`;
    bindNum("f-rvol", state.xo.filters, "minRvol", parseFloat);
    bindNum("f-turn", state.xo.filters, "minTurnover", parseFloat);
    bindChips("c-dir", (v) => (state.xo.filters.dir = v));
    bindChips("c-ma", (v) => (state.xo.filters.ma = v));
    bindChips("c-period", (v) => (state.xo.filters.period = v));
  } else {
    const f = state.bo.filters;
    box.innerHTML = `
      <div class="frow">
        ${chips("c-dir", ["All", "Long", "Short"], f.dir)}
        <span class="shown" id="shown"></span>
      </div>
      ${chips("c-type", TYPES, f.type, TYPE_SHORT)}
      <div class="frow">
        ${field("f-rvol", "Min volume surge", "Volume on the breakout bar vs its normal average (e.g. 2 = at least twice normal)", f.minRvol, 0.1)}
        ${field("f-turn", "Min ₹ cr/day", "Average daily traded value, in ₹ crore", f.minTurnover, 1)}
      </div>`;
    bindNum("f-rvol", state.bo.filters, "minRvol", parseFloat);
    bindNum("f-turn", state.bo.filters, "minTurnover", parseFloat);
    bindChips("c-dir", (v) => (state.bo.filters.dir = v));
    bindChips("c-type", (v) => (state.bo.filters.type = v));
  }
}
function bindNum(id, obj, key, parse) {
  document.getElementById(id).addEventListener("input", (ev) => {
    const v = parse(ev.target.value);
    if (!Number.isNaN(v)) { obj[key] = v; loadList(); }
  });
}
function bindChips(id, set) {
  const box = document.getElementById(id);
  box.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
    set(b.dataset.v);
    box.querySelectorAll("button").forEach((x) => x.classList.toggle("active", x === b));
    loadList();
  }));
}

// ---- list ------------------------------------------------------------------
function renderHead() {
  const head = document.getElementById("list-head");
  const s = state[state.mode].sort;
  head.innerHTML = "";
  const tr = document.createElement("tr");
  cols().forEach((col) => {
    const th = document.createElement("th");
    if (col.l) th.className = "l";
    th.innerHTML = col.label + `<span class="arr">${s.col === col.key ? (s.dir === "asc" ? " ▲" : " ▼") : ""}</span>`;
    th.addEventListener("click", () => {
      const st = state[state.mode].sort;
      if (st.col === col.key) st.dir = st.dir === "asc" ? "desc" : "asc";
      else state[state.mode].sort = { col: col.key, dir: col.l ? "asc" : "desc" };
      loadList();
    });
    tr.appendChild(th);
  });
  head.appendChild(tr);
}

function loadList() {
  const src = { sr: SR, bo: BO, xo: XO }[state.mode];
  const base = src.filter((c) => c.timeframe === state.tf);
  const rows = sortRows(base.filter(PASS[state.mode]));
  renderHead();
  const body = document.getElementById("list-body"), empty = document.getElementById("list-empty");
  document.getElementById("shown").textContent = `${rows.length} of ${base.length} shown`;
  body.innerHTML = "";
  if (!rows.length) {
    empty.style.display = "flex";
    const what = { sr: "setups", bo: "breakouts", xo: "crossovers" }[state.mode];
    empty.textContent = base.length ? "Nothing matches these filters — try loosening them."
      : state.mode === "xo" && state.tf === "1m" ? "Monthly history is too short for a 100+ period average (data starts in 2020)."
      : `No ${what} on this timeframe.`;
    return;
  }
  empty.style.display = "none";
  rows.forEach((c) => {
    const key = rowKey(c);
    const tr = document.createElement("tr");
    tr.dataset.key = key;
    if (key === state.key) tr.classList.add("selected");
    tr.innerHTML = cols().map((col) => `<td class="${col.l ? "l" : "num"}">${col.html(c)}</td>`).join("");
    tr.addEventListener("click", () => selectRow(c));
    body.appendChild(tr);
  });
  selectRow(rows.find((c) => rowKey(c) === state.key) || rows[0]);
}

function selectRow(c) {
  state.key = rowKey(c);
  document.querySelectorAll("table.list tbody tr").forEach((tr) => tr.classList.toggle("selected", tr.dataset.key === state.key));
  loadChart(c);
}

// ---- chart -------------------------------------------------------------------
let chart = null, mainSeries = null, extras = [];
function makeChart() {
  const el = document.getElementById("chart");
  chart = LC.createChart(el, {
    layout: { background: { type: "solid", color: "#11151f" }, textColor: "#98a4b8",
              fontFamily: "Inter, system-ui, sans-serif", fontSize: 11 },
    grid: { vertLines: { color: "#171c29" }, horzLines: { color: "#171c29" } },
    rightPriceScale: { borderColor: "#222a3b" },
    timeScale: { borderColor: "#222a3b", rightOffset: 6 },
    crosshair: { mode: LC.CrosshairMode.Normal },
    autoSize: false,
  });
  const size = () => chart.applyOptions({ width: el.clientWidth, height: el.clientHeight });
  size(); new ResizeObserver(size).observe(el);
}

async function loadChart(c) {
  const res = await fetch(`data/ohlcv/${safeName(c.symbol)}__${c.timeframe}.json`);
  state.cand = c; state.candles = await res.json();
  drawChart(true);
}

function drawChart(fit) {
  const c = state.cand, candles = state.candles;
  if (!c || !candles) return;
  if (mainSeries) chart.removeSeries(mainSeries);
  extras.forEach((s) => chart.removeSeries(s)); extras = [];

  if (state.chartType === "line") {
    mainSeries = chart.addLineSeries({ color: "#98a4b8", lineWidth: 2, priceLineVisible: false, lastValueVisible: true });
    mainSeries.setData(candles.map((k) => ({ time: k.time, value: k.close })));
  } else {
    mainSeries = chart.addCandlestickSeries({ upColor: "#34d399", downColor: "#f87171", wickUpColor: "#34d399",
      wickDownColor: "#f87171", borderVisible: false, priceLineVisible: false });
    mainSeries.setData(candles);
  }

  if (state.mode === "sr") drawSR(c, candles); else if (state.mode === "bo") drawBO(c); else drawXO(c, candles);
  if (fit) {
    if (state.mode === "xo") {
      const n = candles.length;
      chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, n - Math.max(260, c.period + 60)), to: n + 3 });
    } else if (state.mode === "bo") {
      // Breakouts: open zoomed on the recent action (last ~60 candles), widened
      // just enough to include where the earliest level line starts.
      const n = candles.length;
      const starts = c.lines.map((ln) => candles.findIndex((k) => k.time >= ln.from)).filter((i) => i >= 0);
      const from = Math.max(0, Math.min(n - 60, ...(starts.length ? [Math.min(...starts) - 5] : [])));
      chart.timeScale().setVisibleLogicalRange({ from, to: n + 3 });
    } else chart.timeScale().fitContent();
  }
  renderInfo(c);
}

function drawSR(c, candles) {
  const first = c.first_idx, last = c.last_idx;
  if (candles[first] && candles[last]) {
    const s = chart.addLineSeries({ color: "#7c8cff", lineWidth: 2, priceLineVisible: false, lastValueVisible: true, crosshairMarkerVisible: false });
    s.setData([{ time: candles[first].time, value: c.value_now + c.slope * (first - last) }, { time: candles[last].time, value: c.value_now }]);
    extras.push(s);
  }
  if (c.touch_points && c.touch_points.length)
    mainSeries.setMarkers(c.touch_points.map((tp) => ({ time: tp.date, position: c.role === "resistance" ? "aboveBar" : "belowBar",
      color: "#98a4b8", shape: "circle", size: 0.6 })));
}

function drawBO(e) {
  e.lines.forEach((ln) => {
    const dotted = ln.style === "dotted";
    const s = chart.addLineSeries({ color: dotted ? "#5f6b82" : "#7c8cff", lineWidth: dotted ? 1 : 2,
      lineStyle: dotted ? LC.LineStyle.Dotted : LC.LineStyle.Solid,
      priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, title: ln.label });
    s.setData(ln.from === ln.to ? [{ time: ln.to, value: ln.price }] : [{ time: ln.from, value: ln.price }, { time: ln.to, value: ln.price }]);
    extras.push(s);
  });
  mainSeries.createPriceLine({ price: e.invalidation, color: "#f87171", lineStyle: LC.LineStyle.Dashed, lineWidth: 1, axisLabelVisible: true, title: "stop" });
  mainSeries.createPriceLine({ price: e.target, color: "#34d399", lineStyle: LC.LineStyle.Dashed, lineWidth: 1, axisLabelVisible: true, title: "target" });
  const long = e.direction === "Long";
  mainSeries.setMarkers([{ time: e.trigger_date, position: long ? "belowBar" : "aboveBar",
    color: long ? "#34d399" : "#f87171", shape: long ? "arrowUp" : "arrowDown", text: "trigger" }]);
}

// Moving average over closes — must match crossovers.py (sma / ema, SMA-seeded EMA).
function maSeries(candles, type, n) {
  const out = [];
  if (type === "SMA") {
    let s = 0;
    candles.forEach((k, i) => { s += k.close; if (i >= n) s -= candles[i - n].close; if (i >= n - 1) out.push({ time: k.time, value: s / n }); });
  } else {
    if (candles.length < n) return out;
    const k = 2 / (n + 1);
    let e = candles.slice(0, n).reduce((a, c) => a + c.close, 0) / n;
    out.push({ time: candles[n - 1].time, value: e });
    for (let i = n; i < candles.length; i++) { e = (candles[i].close - e) * k + e; out.push({ time: candles[i].time, value: e }); }
  }
  return out;
}

function drawXO(e, candles) {
  const s = chart.addLineSeries({ color: "#7c8cff", lineWidth: 2, priceLineVisible: false, lastValueVisible: true,
    crosshairMarkerVisible: false, title: `${e.ma_type} ${e.period}` });
  s.setData(maSeries(candles, e.ma_type, e.period));
  extras.push(s);
  const up = e.direction === "Bullish";
  mainSeries.setMarkers([{ time: e.cross_date, position: up ? "belowBar" : "aboveBar",
    color: up ? "#34d399" : "#f87171", shape: up ? "arrowUp" : "arrowDown", text: "cross" }]);
}

// ---- info card: plain-English summary + labelled tiles -----------------------
const tile = (k, v, s = "", cls = "") =>
  `<div class="tile"><div class="k">${k}</div><div class="v ${cls}">${v}</div>${s ? `<div class="s">${s}</div>` : ""}</div>`;

function srSummary(c) {
  const kind = c.line_type === "trendline"
    ? (c.slope > 0 ? "a rising" : c.slope < 0 ? "a falling" : "a") + " " + c.role + " trendline"
    : "a flat " + c.role + " level";
  const where = {
    "Support Reversal": "Price is holding above it — a possible bounce.",
    "Support Breakdown": "Price has closed below it — the support has broken.",
    "Resistance Reversal": "Price is holding below it — a possible rejection.",
    "Resistance Breakout": "Price has closed above it — the resistance has broken.",
  }[c.setup] || "";
  return `<b>${sym(c)}</b> is at ${kind} on the ${TF_WORD[c.timeframe]} chart that price has tested <b>${c.touches} times</b>. ${where}`;
}

function boSummary(e) {
  const long = e.direction === "Long", per = TF_BAR[e.timeframe] === "day" ? "week" : "month";
  const what = {
    PREV_HL: long ? `Closed above the previous ${per}'s high (${e.level_name})` : `Closed below the previous ${per}'s low (${e.level_name})`,
    CPR: `Closed ${long ? "above the top (TC)" : "below the bottom (BC)"} of a narrow CPR`,
    HIGH52: e.variant === "ATH" ? "Closed at a new all-time high" : "Closed at a new 52-week high",
    BASE: `Broke out of a tight ${e.variant || "base"} near its highs`,
    NR7: `Broke ${long ? "above the high" : "below the low"} of a ${e.variant} compression bar`,
    GAP: `A ${long ? "gap-up" : "gap-down"} held for 3 sessions and price closed beyond the gap edge`,
  }[e.code] || e.type;
  const vol = e.rvol != null ? ` on a <b>${xfmt(e.rvol)}</b> volume surge` : "";
  return `${what} at <b>${inr(e.level)}</b>. Closed ${inr(e.trigger)} on ${dfmt(e.trigger_date)}${vol}.${e.forming ? " <span class='muted'>(this bar is still forming)</span>" : ""}`;
}

function renderInfo(c) {
  const el = document.getElementById("info");
  if (state.mode === "sr") {
    el.innerHTML = `
      <div class="i-top"><span class="i-sym">${sym(c)}</span><span class="i-ltp price">${inr(c.close)}</span>
        ${setupPill(c.setup)}<span class="pill neutral">${TF_WORD[c.timeframe]}</span></div>
      <div class="i-sum">${srSummary(c)}</div>
      <div class="tiles">
        ${tile("Confidence", Math.round(c.confidence) + "%", "line quality score")}
        ${tile("Touches", c.touches, "times price tested it")}
        ${tile("From the line", signed(c.distance_atr) + " ATR", "0 = right on it")}
        ${tile("Volume", xfmt(c.vol_ratio), volSub(c.timeframe), c.vol_ratio >= 1.5 ? "up" : "")}
        ${tile("Turnover", c.turnover_cr == null ? "—" : "₹" + c.turnover_cr + " cr", "avg per day")}
        ${tile("Last touch", dfmt(c.last_touch))}
      </div>`;
  } else if (state.mode === "xo") {
    const up = c.direction === "Bullish";
    el.innerHTML = `
      <div class="i-top"><span class="i-sym">${sym(c)}</span><span class="i-ltp price">${inr(c.close)}</span>
        <span class="pill ${up ? "up" : "down"}">${c.direction}</span>
        <span class="pill neutral">${c.ma_type} ${c.period}</span>
        <span class="pill neutral">${TF_WORD[c.timeframe]}</span></div>
      <div class="i-sum">Closed <b>${up ? "above" : "below"}</b> its ${c.period}-${TF_BAR[c.timeframe]} ${c.ma_type} on ${dfmt(c.cross_date)}
        (close ${inr(c.cross_close)} vs average ${inr(c.cross_ma)})${c.rvol != null ? ` on a <b>${xfmt(c.rvol)}</b> volume surge` : ""}.${c.forming ? " <span class='muted'>(this bar is still forming)</span>" : ""}</div>
      <div class="tiles">
        ${tile(`${c.ma_type} ${c.period} now`, inr(c.ma_value), "the average today")}
        ${tile("Price vs average", signed(c.dist_pct) + "%", up ? "above the line" : "below the line", up ? "up" : "down")}
        ${tile("Volume surge", xfmt(c.rvol) + " normal", `vs last ${RVOL_N[c.timeframe]} ${TF_BAR[c.timeframe]}s`, c.rvol >= 1.5 ? "up" : "")}
        ${tile("Crossed", dfmt(c.cross_date), firedText(c))}
      </div>`;
  } else {
    const long = c.direction === "Long";
    el.innerHTML = `
      <div class="i-top"><span class="i-sym">${sym(c)}</span><span class="i-ltp price">${inr(c.close)}</span>
        <span class="pill ${long ? "up" : "down"}">${c.direction}</span>
        <span class="pill neutral">${c.type}${c.variant && c.code !== "HIGH52" ? " · " + c.variant : ""}</span>
        <span class="pill neutral">${TF_WORD[c.timeframe]}</span></div>
      <div class="i-sum">${boSummary(c)}</div>
      <div class="tiles">
        ${tile("Entry (trigger)", inr(c.trigger), "the closing price")}
        ${tile("Stop", inr(c.invalidation), "setup fails below/above this", "down")}
        ${tile("Target (1R)", inr(c.target), "entry ± the risk distance", "up")}
        ${tile("Risk", c.r_pct + "%", inr(c.r) + " per share")}
        ${tile("Volume surge", xfmt(c.rvol) + " normal", `vs last ${RVOL_N[c.timeframe]} ${TF_BAR[c.timeframe]}s`, c.rvol >= 1.5 ? "up" : "")}
        ${tile("Fired", dfmt(c.trigger_date), firedText(c))}
      </div>
      ${c.context && c.code !== "PREV_HL" ? `<div class="note">${c.context}${c.extrapolated ? " · * weekly rule applied to monthly bars" : ""}</div>` : ""}`;
  }
}

// ---- toggles / boot ----------------------------------------------------------
function setActive(box, attr, val) {
  document.querySelectorAll(`${box} button`).forEach((b) => b.classList.toggle("active", b.dataset[attr] === val));
}
function setupToggles() {
  document.querySelectorAll("#mode-toggle button").forEach((b) => b.addEventListener("click", () => {
    if (b.dataset.mode === state.mode) return;
    state.mode = b.dataset.mode; state.key = null; state.cand = null;
    setActive("#mode-toggle", "mode", state.mode);
    renderFilters(); loadList();
  }));
  document.querySelectorAll("#tf-toggle button").forEach((b) => b.addEventListener("click", () => {
    if (b.dataset.tf === state.tf) return;
    state.tf = b.dataset.tf; setActive("#tf-toggle", "tf", state.tf); loadList();
  }));
  document.querySelectorAll("#ct button").forEach((b) => b.addEventListener("click", () => {
    if (b.dataset.ct === state.chartType) return;
    state.chartType = b.dataset.ct; setActive("#ct", "ct", state.chartType); drawChart(false);
  }));
}

window.addEventListener("DOMContentLoaded", () => {
  makeChart(); setupToggles();
  const q = new URLSearchParams(location.search);
  if (["1d", "1w", "1m"].includes(q.get("tf"))) { state.tf = q.get("tf"); setActive("#tf-toggle", "tf", state.tf); }
  if (["bo", "xo"].includes(q.get("mode"))) { state.mode = q.get("mode"); setActive("#mode-toggle", "mode", state.mode); }
  loadAll(); loadMeta();
});
