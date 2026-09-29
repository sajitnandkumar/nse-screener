/* NSE Breakouts — static frontend for the breakout library (breakout_library.md).
   Reads data/breakouts.json (built by build_site.py via breakouts.py). Each row is a
   full trade card (level, trigger, invalidation, R, target) plus the level lines to
   draw, so a click only needs that stock's candles. */

const LC = LightweightCharts;
const TYPES = ["All", "Previous High / Low", "CPR Breakout", "52-Week High / ATH",
               "Base Breakout", "NR7 / Inside Bar", "Gap-and-Go"];

const SHORT = { "Previous High / Low": "Prev H/L", "CPR Breakout": "CPR", "52-Week High / ATH": "52WH/ATH",
  "Base Breakout": "Base", "NR7 / Inside Bar": "NR7/Inside", "Gap-and-Go": "Gap&Go" };

const state = {
  tf: "1d", key: null,
  filters: { dir: "All", type: "All", minRvol: 0, minTurnover: 5 },
  sort: { col: "fired", dir: "asc" },   // newest first
};
let ALL = [];

const safeName = (s) => s.replace(/[^A-Za-z0-9]/g, "_");   // matches build_site._safe
const fmtPrice = (n) => (n == null ? "—" : n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
const rowKey = (e) => `${e.symbol}:${e.code}:${e.timeframe}:${e.direction}:${e.trigger_date}:${e.level}`;
const firedText = (e) => (e.forming ? "live" : e.bars_ago === 0 ? "latest" : `${e.bars_ago} bar${e.bars_ago > 1 ? "s" : ""} ago`);

const COLUMNS = [
  { key: "symbol", label: "Symbol", align: "l", get: (e) => e.symbol.replace("-EQ", ""), sort: (e) => e.symbol, cell: "l sym" },
  { key: "close", label: "LTP", num: true, get: (e) => fmtPrice(e.close), sort: (e) => e.close },
  { key: "type", label: "Breakout", align: "l", get: (e) => e.type + (e.variant && e.code !== "HIGH52" ? ` · ${e.variant}` : "") + (e.extrapolated ? " *" : ""),
    sort: (e) => e.type, cell: "l setup" },
  { key: "level_name", label: "Level", align: "l", get: (e) => e.level_name, sort: (e) => e.level_name, cell: "l dim" },
  { key: "direction", label: "Dir", align: "l", get: (e) => e.direction, sort: (e) => e.direction,
    cell: "l", cellCls: (e) => (e.direction === "Long" ? "price-up" : "price-down") },
  { key: "trigger", label: "Trigger", num: true, get: (e) => fmtPrice(e.trigger), sort: (e) => e.trigger },
  { key: "r_pct", label: "R%", num: true, get: (e) => e.r_pct.toFixed(1) + "%", sort: (e) => e.r_pct },
  { key: "rvol", label: "RVOL", num: true, get: (e) => (e.rvol == null ? "—" : e.rvol.toFixed(1) + "×"), sort: (e) => e.rvol ?? -1,
    cellCls: (e) => (e.rvol >= 1.5 ? "price-up" : "dim") },
  { key: "fired", label: "Fired", num: true, get: (e) => firedText(e), sort: (e) => e.bars_ago, cell: "" },
];

function passesFilters(e) {
  const f = state.filters;
  if (f.dir !== "All" && e.direction !== f.dir) return false;
  if (f.type !== "All" && e.type !== f.type) return false;
  if (f.minRvol > 0 && (e.rvol ?? 0) < f.minRvol) return false;
  if ((e.turnover_cr ?? 0) < f.minTurnover) return false;
  return true;
}

function sortRows(rows) {
  const col = COLUMNS.find((x) => x.key === state.sort.col) || COLUMNS[8];
  const mul = state.sort.dir === "asc" ? 1 : -1;
  return rows.sort((a, b) => {
    const va = col.sort(a), vb = col.sort(b);
    const r = typeof va === "string" ? va.localeCompare(vb) : va - vb;
    return r !== 0 ? mul * r : (b.rvol ?? 0) - (a.rvol ?? 0);   // tie-break: strongest volume
  });
}

async function loadAll() {
  ALL = await fetch("data/breakouts.json").then((r) => r.json());
  loadList();
}

async function loadMeta() {
  try {
    const m = await fetch("data/meta.json").then((r) => r.json());
    const bits = [];
    if (m.data_through) bits.push(`data through ${m.data_through}`);
    if (m.generated_at) bits.push(`built ${m.generated_at}`);
    document.getElementById("generated").textContent = bits.join("  ·  ");
  } catch (e) { /* optional */ }
}

function renderHead() {
  const head = document.getElementById("list-head");
  head.innerHTML = "";
  const tr = document.createElement("tr");
  COLUMNS.forEach((col) => {
    const th = document.createElement("th");
    if (col.align === "l") th.className = "l";
    const arrow = state.sort.col === col.key ? (state.sort.dir === "asc" ? " ▲" : " ▼") : "";
    th.innerHTML = col.label + `<span class="arr">${arrow}</span>`;
    th.addEventListener("click", () => {
      if (state.sort.col === col.key) state.sort.dir = state.sort.dir === "asc" ? "desc" : "asc";
      else state.sort = { col: col.key, dir: col.num ? "desc" : "asc" };
      loadList();
    });
    tr.appendChild(th);
  });
  head.appendChild(tr);
}

function loadList() {
  const base = ALL.filter((e) => e.timeframe === state.tf);
  const rows = sortRows(base.filter(passesFilters));
  renderHead();
  const body = document.getElementById("list-body");
  const empty = document.getElementById("list-empty");
  document.getElementById("shown-count").textContent = `${rows.length} of ${base.length} shown`;
  body.innerHTML = "";
  if (!rows.length) {
    empty.style.display = "flex";
    empty.textContent = base.length ? "No breakouts match the filters — loosen them." : "No breakouts on this timeframe.";
    return;
  }
  empty.style.display = "none";
  rows.forEach((e) => {
    const key = rowKey(e);
    const tr = document.createElement("tr");
    tr.dataset.key = key;
    if (key === state.key) tr.classList.add("selected");
    tr.innerHTML = COLUMNS.map((col) => {
      const cls = [col.cell || "", col.cellCls ? col.cellCls(e) : ""].join(" ").trim();
      return `<td${cls ? ` class="${cls}"` : ""}>${col.get(e)}</td>`;
    }).join("");
    tr.addEventListener("click", () => selectRow(e));
    body.appendChild(tr);
  });
  selectRow(rows.find((e) => rowKey(e) === state.key) || rows[0]);
}

function setupFilters() {
  const bind = (id, key) => {
    const el = document.getElementById(id);
    el.value = state.filters[key];
    el.addEventListener("input", () => {
      const v = parseFloat(el.value);
      if (!Number.isNaN(v)) { state.filters[key] = v; loadList(); }
    });
  };
  bind("f-rvol", "minRvol");
  bind("f-turn", "minTurnover");

  const chip = (container, dataKey, stateKey) =>
    container.querySelectorAll("button").forEach((btn) =>
      btn.addEventListener("click", () => {
        state.filters[stateKey] = btn.dataset[dataKey];
        container.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b === btn));
        loadList();
      }));
  chip(document.getElementById("f-dir"), "d", "dir");

  const typeBox = document.getElementById("f-type");
  typeBox.innerHTML = TYPES.map((t, i) => `<button data-t="${t}"${i ? "" : ' class="active"'}>${SHORT[t] || t}</button>`).join("");
  chip(typeBox, "t", "type");
}

function selectRow(e) {
  state.key = rowKey(e);
  document.querySelectorAll("table.list tr").forEach((tr) =>
    tr.classList.toggle("selected", tr.dataset.key === state.key));
  loadChart(e);
}

// ---- chart -------------------------------------------------------------
let chart = null, mainSeries = null, extras = [], priceLines = [];

function makeChart() {
  const el = document.getElementById("chart");
  chart = LC.createChart(el, {
    layout: { background: { type: "solid", color: "#0b0e13" }, textColor: "#8a95a3",
              fontFamily: "ui-monospace, Menlo, monospace", fontSize: 11 },
    grid: { vertLines: { color: "#141a22" }, horzLines: { color: "#141a22" } },
    rightPriceScale: { borderColor: "#232b36" },
    timeScale: { borderColor: "#232b36", rightOffset: 6 },
    crosshair: { mode: LC.CrosshairMode.Normal },
    autoSize: false,
  });
  const size = () => chart.applyOptions({ width: el.clientWidth, height: el.clientHeight });
  size();
  new ResizeObserver(size).observe(el);
}

async function loadChart(e) {
  const candles = await fetch(`data/ohlcv/${safeName(e.symbol)}__${e.timeframe}.json`).then((r) => r.json());
  if (mainSeries) chart.removeSeries(mainSeries);
  extras.forEach((s) => chart.removeSeries(s));
  extras = []; priceLines = [];

  mainSeries = chart.addCandlestickSeries({
    upColor: "#2ea06a", downColor: "#e0554e", wickUpColor: "#2ea06a", wickDownColor: "#e0554e",
    borderVisible: false, priceLineVisible: false,
  });
  mainSeries.setData(candles);

  // Level lines (BH/BL, TC/BC/P, PWH, setup high/low, ...) over their own span.
  e.lines.forEach((ln) => {
    const s = chart.addLineSeries({
      color: ln.style === "dotted" ? "#5b6570" : "#e6edf3", lineWidth: ln.style === "dotted" ? 1 : 2,
      lineStyle: ln.style === "dotted" ? LC.LineStyle.Dotted : LC.LineStyle.Solid,
      priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
      title: ln.label,
    });
    s.setData(ln.from === ln.to ? [{ time: ln.to, value: ln.price }]
                                : [{ time: ln.from, value: ln.price }, { time: ln.to, value: ln.price }]);
    extras.push(s);
  });

  // Trade card: invalidation (red dashed) and 1R target (green dashed).
  priceLines.push(mainSeries.createPriceLine({ price: e.invalidation, color: "#e0554e",
    lineStyle: LC.LineStyle.Dashed, lineWidth: 1, axisLabelVisible: true, title: "invalid" }));
  priceLines.push(mainSeries.createPriceLine({ price: e.target, color: "#2ea06a",
    lineStyle: LC.LineStyle.Dashed, lineWidth: 1, axisLabelVisible: true, title: "target 1R" }));

  const long = e.direction === "Long";
  mainSeries.setMarkers([{ time: e.trigger_date, position: long ? "belowBar" : "aboveBar",
    color: long ? "#2ea06a" : "#e0554e", shape: long ? "arrowUp" : "arrowDown", text: "trigger" }]);

  chart.timeScale().fitContent();
  renderHeader(e);
}

function renderHeader(e) {
  const sep = `<span class="h-meta dim">·</span>`;
  const long = e.direction === "Long";
  document.getElementById("chart-header-text").innerHTML = `
    <span class="h-sym">${e.symbol.replace("-EQ", "")}</span>
    <span class="h-meta ltp">${fmtPrice(e.close)}</span>
    <span class="h-setup">${e.type}${e.variant ? " · " + e.variant : ""}</span>
    <span class="h-meta ${long ? "price-up" : "price-down"}">${e.direction}</span>
    ${sep}<span class="h-meta">${e.level_name} <b>${fmtPrice(e.level)}</b></span>
    ${sep}<span class="h-meta">trigger <b>${fmtPrice(e.trigger)}</b></span>
    ${sep}<span class="h-meta">invalid <b>${fmtPrice(e.invalidation)}</b></span>
    ${sep}<span class="h-meta">R <b>${fmtPrice(e.r)}</b> (${e.r_pct}%)</span>
    ${sep}<span class="h-meta">target 1R <b>${fmtPrice(e.target)}</b></span>
    ${sep}<span class="h-meta">RVOL <b>${e.rvol == null ? "—" : e.rvol.toFixed(1) + "×"}</b></span>
    ${sep}<span class="h-meta">fired <b>${e.trigger_date}</b>${e.forming ? " (bar still forming)" : ""}</span>
    ${e.context ? `${sep}<span class="h-meta">${e.context}</span>` : ""}
    ${e.extrapolated ? `${sep}<span class="h-meta">* weekly rule applied to monthly bars</span>` : ""}`;
}

function setupToggle() {
  document.querySelectorAll("#tf-toggle button").forEach((btn) =>
    btn.addEventListener("click", () => {
      if (btn.dataset.tf === state.tf) return;
      state.tf = btn.dataset.tf;
      document.querySelectorAll("#tf-toggle button").forEach((b) => b.classList.toggle("active", b === btn));
      loadList();
    }));
}

window.addEventListener("DOMContentLoaded", () => {
  makeChart(); setupToggle(); setupFilters();
  const tf = new URLSearchParams(location.search).get("tf");
  if (["1d", "1w", "1m"].includes(tf)) {
    state.tf = tf;
    document.querySelectorAll("#tf-toggle button").forEach((b) => b.classList.toggle("active", b.dataset.tf === tf));
  }
  loadAll(); loadMeta();
});
