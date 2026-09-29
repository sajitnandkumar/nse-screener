/* Backtest page — plain-English view of data/backtest.json.
   Each row = one historical moment a stock sat on a trendline (walk-forward, no
   lookahead): held (rev=1) or broke, plus the % price move at each look-ahead
   horizon. Everything is aggregated here in the browser. */

const LC = LightweightCharts;
const safeName = (s) => s.replace(/[^A-Za-z0-9]/g, "_");
const MON = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const dfmt = (s) => { const [y, m, d] = s.slice(0, 10).split("-"); return `${+d} ${MON[+m - 1]} ${y}`; };
const nfmt = (n) => n.toLocaleString("en-IN");
const pct = (x, d = 1) => (x == null ? "—" : (x >= 0 ? "+" : "") + x.toFixed(d) + "%");
const sym = (s) => s.replace("-EQ", "");

let ALL = [], ROWS = [], META = {};
const range = { from: null, to: null };
const state = { h: 2 };                      // index into META.ret_bars
let DRILL = null, chart = null, cSeries = null, lSeries = null, selKey = null;

// Plain words per setup category. A support bounce is a buy; a resistance
// rejection is a short, so for it a price DROP is the good outcome.
const CAT = {
  "Support Reversal":    { title: "Buying a support bounce",        held: "Bounced",  broke: "Broke down", good: +1,
                           what: "price was sitting on a support trendline" },
  "Resistance Reversal": { title: "Shorting a resistance rejection", held: "Rejected", broke: "Broke out",  good: -1,
                           what: "price was sitting under a resistance trendline" },
};
const goodCls = (x, cat) => (x == null ? "dim" : x * CAT[cat].good >= 0 ? "up" : "down");
const TOUCH_BANDS = [["6–7 touches", 6, 8], ["8–9 touches", 8, 10], ["10–12 touches", 10, 13], ["13+ touches", 13, 999]];

const heldPct = (rows) => (rows.length ? (100 * rows.filter((r) => r.rev).length) / rows.length : null);
const avg = (rows, i) => (rows.length ? rows.reduce((s, r) => s + r.rets[i], 0) / rows.length : null);
const cat = (c) => ROWS.filter((r) => r.su === c);
const H = () => META.ret_bars[state.h];
const hWord = () => `${H()} candle${H() > 1 ? "s" : ""}`;

async function load() {
  const j = await (await fetch("data/backtest.json")).json();
  ALL = j.rows; META = j.meta;
  state.h = META.ret_bars.length - 1;
  range.from = META.dmin; range.to = META.dmax;
  buildControls(); buildDates(); makeChart(); applyRange();
}

function buildControls() {
  const host = document.getElementById("c-h"); host.innerHTML = "";
  META.ret_bars.forEach((k, i) => {
    const b = document.createElement("button");
    b.textContent = `${k} candle${k > 1 ? "s" : ""}`;
    b.className = i === state.h ? "active" : "";
    b.addEventListener("click", () => {
      state.h = i;
      host.querySelectorAll("button").forEach((x) => x.classList.toggle("active", x === b));
      render();
    });
    host.appendChild(b);
  });
}

function buildDates() {
  ["from", "to"].forEach((k) => {
    const el = document.getElementById("d-" + k);
    el.min = META.dmin; el.max = META.dmax; el.value = range[k];
    el.addEventListener("change", () => {
      if (!el.value) return;
      range[k] = el.value;
      if (range.from > range.to) { range[k === "from" ? "to" : "from"] = el.value; document.getElementById("d-" + (k === "from" ? "to" : "from")).value = el.value; }
      applyRange();
    });
  });
}

// Filter every case by its as-of date, then redraw everything from that subset.
function applyRange() {
  ROWS = ALL.filter((r) => r.dt >= range.from && r.dt <= range.to);
  DRILL = null; selKey = null;
  document.getElementById("drill-empty").style.display = "";
  document.getElementById("drill-table").style.display = "none";
  document.getElementById("drill-title").textContent = "Cases";
  document.getElementById("stamp").textContent = `${nfmt(ROWS.length)} cases · ${dfmt(range.from)} → ${dfmt(range.to)}`;
  render();
}

function render() {
  document.getElementById("intro").textContent = `Do trendline setups work? · ${nfmt(ROWS.length)} past setups`;
  renderVerdicts(); renderConf(); renderSlices(); renderMethod();
  if (DRILL) renderDrill();
}

// ---- verdict cards ----------------------------------------------------------
const tile = (k, v, s, cls = "") => `<div class="tile"><div class="k">${k}</div><div class="v ${cls}">${v}</div><div class="s">${s}</div></div>`;

const dirOf = (r) => (r.lt === "horizontal" ? "flat" : r.sl > 0 ? "rising" : "falling");

function renderVerdicts() {
  const el = document.getElementById("verdicts"); el.innerHTML = "";
  // Four cards: support / resistance x rising / falling line. Flat lines (few) stay in the table below.
  META.cats.forEach((c) => ["rising", "falling"].forEach((d) => {
    const P = CAT[c], rows = cat(c).filter((r) => dirOf(r) === d);
    const held = rows.filter((r) => r.rev), broke = rows.filter((r) => !r.rev);
    const a = avg(rows, state.h), ah = avg(held, state.h), ab = avg(broke, state.h), hp = heldPct(rows);
    const goodAll = a != null && a * P.good > 0;
    const say = c.startsWith("Support")
      ? (goodAll ? "Bounces rare but big. <b>Net positive.</b>" : "Breaks outweigh bounces. <b>No edge.</b>")
      : (goodAll ? "Rejections dominate. <b>Works as a short.</b>" : "Most break out and rise. <b>Weak as a short.</b>");
    const side = c.split(" ")[0], arrow = d === "rising" ? "↗" : "↘";
    el.insertAdjacentHTML("beforeend", `
      <div class="card verdict ${rows.length < 100 ? "thin" : ""}">
        <div class="head"><span class="t">${side} · ${d} line ${arrow}</span><span class="n">${nfmt(rows.length)} cases</span></div>
        <div><div class="big ${goodCls(a, c)}">${pct(a)}</div><div class="k">avg move after ${hWord()}</div></div>
        <div class="tiles three">
          ${tile(P.held, hp == null ? "—" : hp.toFixed(0) + "%", "held the line")}
          ${tile("When held", pct(ah), "avg move", goodCls(ah, c))}
          ${tile("When broke", pct(ab), "avg move", goodCls(ab, c))}
        </div>
        <div class="say">${say}</div>
      </div>`);
  }));
}

// ---- confidence bands ------------------------------------------------------
const hbar = (v, max) => `<span class="hbar"><b style="width:${Math.max(0, Math.min(100, (100 * (v || 0)) / max))}%"></b></span>`;

function renderConf() {
  const wrap = document.getElementById("conf-wrap"); wrap.innerHTML = "";
  const notes = [];
  META.cats.forEach((c) => {
    const rows = cat(c), P = CAT[c];
    const bands = META.bands.map(([lab, lo, hi]) => {
      const b = rows.filter((r) => r.c >= lo && r.c < hi);
      return { lab, lo, hi, n: b.length, hp: heldPct(b), mv: avg(b, state.h) };
    });
    const maxHp = Math.max(...bands.map((b) => b.hp || 0), 1);
    let h = `<div><div class="muted" style="margin-bottom:6px;font-weight:600">${P.title}</div><table class="bt">
      <thead><tr><th class="l">Confidence</th><th>Cases</th><th class="l">${P.held}</th><th>Move</th></tr></thead><tbody>`;
    bands.forEach((b) => {
      h += `<tr class="click ${b.n && b.n < 100 ? "thin" : ""}" data-c="${c}" data-lo="${b.lo}" data-hi="${b.hi}" data-lab="${b.lab}">
        <td class="l">${b.lab.replace("<70", "under 70")}${b.lab === "<70" ? "" : "%"}</td><td>${nfmt(b.n)}</td>
        <td class="l">${hbar(b.hp, maxHp)}${b.hp == null ? "—" : b.hp.toFixed(0) + "%"}</td>
        <td class="${goodCls(b.mv, c)}">${pct(b.mv)}</td></tr>`;
    });
    wrap.insertAdjacentHTML("beforeend", h + "</tbody></table></div>");
    const ok = bands.filter((b) => b.n >= 100);
    const mono = ok.every((b, i) => i === 0 || b.hp >= ok[i - 1].hp - 0.5);
    notes.push(`<b>${P.title}:</b> ${mono
      ? `yes — held ${ok[0].hp.toFixed(0)}% → ${ok[ok.length - 1].hp.toFixed(0)}%, move ${pct(ok[0].mv)} → ${pct(ok[ok.length - 1].mv)}.`
      : `mixed.`}`);
  });
  document.getElementById("conf-say").innerHTML = notes.join("<br>");
  wrap.querySelectorAll("tr.click").forEach((tr) => tr.addEventListener("click", () => {
    const { c, lo, hi, lab } = tr.dataset;
    select(tr, `${CAT[c].title} · confidence ${lab}`, ROWS.filter((r) => r.su === c && r.c >= +lo && r.c < +hi), c);
  }));
}

// ---- breakdown slices ---------------------------------------------------------
function renderSlices() {
  const slices = [];
  const add = (grp, lab, rows) => rows.length && slices.push({ grp, lab, rows });
  [["1d", "Daily chart"], ["1w", "Weekly chart"], ["1m", "Monthly chart"]].forEach(([tf, lab]) => add("Timeframe", lab, ROWS.filter((r) => r.tf === tf)));
  // Line direction: sign of the slope (flat lines are the "horizontal" type).
  const dir = (r) => (r.lt === "horizontal" ? "flat" : r.sl > 0 ? "rising" : "falling");
  [["support", "Support"], ["resistance", "Resistance"]].forEach(([sd, lab]) => {
    add("Line direction", `${lab} — rising (uptrend)`, ROWS.filter((r) => r.sd === sd && dir(r) === "rising"));
    add("Line direction", `${lab} — falling (downtrend)`, ROWS.filter((r) => r.sd === sd && dir(r) === "falling"));
    add("Line direction", `${lab} — flat`, ROWS.filter((r) => r.sd === sd && dir(r) === "flat"));
  });
  TOUCH_BANDS.forEach(([lab, lo, hi]) => add("Times tested", lab, ROWS.filter((r) => r.tc >= lo && r.tc < hi)));
  const maxHp = Math.max(...slices.map((s) => heldPct(s.rows) || 0), 1);

  let h = `<thead><tr><th class="l">&nbsp;</th><th>Cases</th><th class="l">Held</th><th>Move</th></tr></thead><tbody>`;
  let last = null;
  slices.forEach((s, i) => {
    if (s.grp !== last) { h += `<tr class="grp"><td class="l" colspan="4">${s.grp}</td></tr>`; last = s.grp; }
    const hp = heldPct(s.rows), mv = avg(s.rows, state.h);
    h += `<tr class="click ${s.rows.length < 100 ? "thin" : ""}" data-i="${i}"><td class="l">${s.lab}</td><td>${nfmt(s.rows.length)}</td>
      <td class="l">${hbar(hp, maxHp)}${hp.toFixed(0)}%</td><td class="${mv >= 0 ? "up" : "down"}">${pct(mv)}</td></tr>`;
  });
  const t = document.getElementById("slices"); t.innerHTML = h + "</tbody>";
  t.querySelectorAll("tr.click").forEach((tr) => tr.addEventListener("click", () => {
    const s = slices[+tr.dataset.i]; select(tr, `${s.grp}: ${s.lab}`, s.rows, null);
  }));
}

function renderMethod() {
  document.getElementById("method").innerHTML = `
    <li><b>No peeking</b> — each line uses only prices available on that day.</li>
    <li><b>Broke</b> = closed clearly through the line within ${META.classify_window} candles; otherwise <b>held</b>.</li>
    <li><b>Move</b> = % change in close after the chosen look-ahead. For a resistance short, a fall is good (colours flipped).</li>
    <li><b>Faded rows</b> = under 100 cases; don't trust them.</li>
    <li>Showing ${dfmt(range.from)} → ${dfmt(range.to)} · ${nfmt(ROWS.length)} of ${nfmt(META.n)} cases · bounce/rejection setups only.</li>`;
}

// ---- drill-down -------------------------------------------------------------------
const keyOf = (r) => `${r.sym}:${r.tf}:${r.dt}:${r.vn}`;

function select(tr, label, rows, c) {
  document.querySelectorAll("tr.sel").forEach((x) => x.classList.remove("sel"));
  tr.classList.add("sel");
  DRILL = { label, rows: rows.slice(), cat: c }; selKey = null;
  renderDrill();
  document.getElementById("drill").scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderDrill() {
  const rows = DRILL.rows.sort((a, b) => b.c - a.c), CAP = 300, shown = rows.slice(0, CAP);
  document.getElementById("drill-empty").style.display = "none";
  document.getElementById("drill-table").style.display = "";
  document.getElementById("drill-title").textContent =
    `Cases — ${DRILL.label} (${nfmt(rows.length)}${rows.length > CAP ? ", top 300" : ""})`;
  document.getElementById("drill-mv-th").textContent = "Move";
  document.getElementById("drill-body").innerHTML = shown.map((r) => {
    const P = CAT[r.su], mv = r.rets[state.h];
    return `<tr class="click ${keyOf(r) === selKey ? "sel" : ""}"><td class="l"><span class="sym">${sym(r.sym)}</span></td><td class="l muted">${dfmt(r.dt)}</td>
      <td>${Math.round(r.c)}%</td><td><span class="pill ${r.rev ? "up" : "down"}">${r.rev ? P.held : P.broke}</span></td>
      <td class="${goodCls(mv, r.su)}">${pct(mv)}</td></tr>`;
  }).join("");
  document.querySelectorAll("#drill-body tr").forEach((tr, i) => tr.addEventListener("click", () => drawCase(shown[i])));
}

function makeChart() {
  const el = document.getElementById("drill-chart");
  chart = LC.createChart(el, {
    layout: { background: { type: "solid", color: "#11151f" }, textColor: "#98a4b8", fontFamily: "Inter, system-ui, sans-serif", fontSize: 11 },
    grid: { vertLines: { color: "#171c29" }, horzLines: { color: "#171c29" } },
    rightPriceScale: { borderColor: "#222a3b" }, timeScale: { borderColor: "#222a3b" },
    width: el.clientWidth || 600, height: 360,
  });
  new ResizeObserver(() => chart.applyOptions({ width: el.clientWidth })).observe(el);
}

async function drawCase(r) {
  selKey = keyOf(r); renderDrill();
  const candles = await (await fetch(`data/ohlcv/${safeName(r.sym)}__${r.tf}.json`)).json();
  const fwd = Math.max(...META.ret_bars, META.classify_window);
  const a = Math.max(0, r.fi - 20), z = Math.min(candles.length - 1, r.li + fwd + 5);
  if (cSeries) chart.removeSeries(cSeries);
  if (lSeries) chart.removeSeries(lSeries);
  cSeries = chart.addCandlestickSeries({ upColor: "#34d399", downColor: "#f87171", wickUpColor: "#34d399", wickDownColor: "#f87171", borderVisible: false, priceLineVisible: false });
  cSeries.setData(candles.slice(a, z + 1));
  const lv = (i) => r.vn + r.sl * (i - r.li), endI = Math.min(candles.length - 1, r.li + fwd);
  lSeries = chart.addLineSeries({ color: "#7c8cff", lineWidth: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
  lSeries.setData([{ time: candles[r.fi].time, value: lv(r.fi) }, { time: candles[endI].time, value: lv(endI) }]);
  cSeries.setMarkers([{ time: candles[r.li].time, position: "aboveBar", color: "#fbbf24", shape: "arrowDown", text: "setup fired" }]);
  chart.timeScale().fitContent();

  const P = CAT[r.su], TF = { "1d": "daily", "1w": "weekly", "1m": "monthly" }[r.tf];
  document.getElementById("drill-hdr").innerHTML =
    `<span class="sym">${sym(r.sym)}</span><span class="pill neutral">${TF}</span><span class="pill ${r.rev ? "up" : "down"}">${r.rev ? P.held : P.broke}</span>` +
    `<span class="muted">fired ${dfmt(r.dt)} · confidence ${Math.round(r.c)}% · move after ${META.ret_bars.map((k, i) =>
      `${k}: <b class="${goodCls(r.rets[i], r.su)}">${pct(r.rets[i])}</b>`).join(", ")}</span>`;
}

window.addEventListener("DOMContentLoaded", load);
