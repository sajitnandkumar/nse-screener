/* Backtest — reversal/break + forward-return model. Reads data/backtest.json
   (per-instance: reversed flag + signed close-to-close returns at each horizon) and
   aggregates client-side. The "forward window" chip picks which horizon the cards /
   CONF panel / breakdown feature; the outcome table shows all horizons. */

const LC = LightweightCharts;
const safeName = (s) => s.replace(/[^A-Za-z0-9]/g, "_");

let ROWS = [], META = {};
const state = { h: 2 };                 // index into ret_bars (default = longest)
let DRILL = null, p5chart = null, p5main = null, p5line = null, p5sel = null;
const TOUCH_BANDS = [["6–7", 6, 8], ["8–9", 8, 10], ["10–12", 10, 13], ["13+", 13, 999]];

const fmtPct = (x) => (x == null ? "—" : (x >= 0 ? "+" : "") + x.toFixed(1) + "%");
const clsSign = (x) => (x == null ? "dimc" : x >= 0 ? "up" : "down");
const cat = (c) => ROWS.filter((r) => r.su === c);
const revPct = (rows) => (rows.length ? (100 * rows.filter((r) => r.rev).length) / rows.length : null);

function stat(rows, i) {
  if (!rows.length) return { n: 0, avg: null, med: null };
  const xs = rows.map((r) => r.rets[i]).sort((a, b) => a - b);
  return { n: xs.length, avg: xs.reduce((s, x) => s + x, 0) / xs.length, med: xs[Math.floor((xs.length - 1) / 2)] };
}

async function load() {
  const j = await (await fetch("data/backtest.json")).json();
  ROWS = j.rows; META = j.meta;
  state.h = META.ret_bars.length - 1;
  buildControls(); makeChart(); render();
}

function buildControls() {
  const host = document.getElementById("c-h"); host.innerHTML = "";
  META.ret_bars.forEach((k, i) => {
    const b = document.createElement("button");
    b.textContent = k + (k === 1 ? " candle" : " candles");
    b.className = i === state.h ? "active" : "";
    b.addEventListener("click", () => {
      state.h = i;
      host.querySelectorAll("button").forEach((x) => x.classList.toggle("active", x === b));
      render();
    });
    host.appendChild(b);
  });
}

function render() {
  document.getElementById("bt-meta").textContent =
    `${META.n.toLocaleString("en-IN")} setups · ${META.dmin} → ${META.dmax} · break = >${META.break_buffer_atr} ATR within ${META.classify_window}`;
  renderCards(); renderVerdict(); renderP2(); renderP3(); renderP4(); renderCov();
  if (DRILL) renderDrill();
}

function renderCards() {
  const el = document.getElementById("p1-cards"); el.innerHTML = "";
  META.cats.forEach((c) => {
    const s = cat(c), all = stat(s, state.h), rp = revPct(s);
    const rv = stat(s.filter((r) => r.rev), state.h), bk = stat(s.filter((r) => !r.rev), state.h);
    el.insertAdjacentHTML("beforeend", `
      <div class="card">
        <div class="ct">${c} · n=${s.length.toLocaleString("en-IN")}</div>
        <div class="big ${clsSign(all.avg)}">${fmtPct(all.avg)}</div>
        <div class="lbl">avg move @${META.ret_bars[state.h]} candles — all setups (expectancy)</div>
        <div class="row2">
          <div><div class="big" style="font-size:18px">${rp == null ? "—" : rp.toFixed(0) + "%"}</div><div class="lbl">reversed</div></div>
          <div><div class="big ${clsSign(rv.avg)}" style="font-size:18px">${fmtPct(rv.avg)}</div><div class="lbl">when reversed</div></div>
          <div><div class="big ${clsSign(bk.avg)}" style="font-size:18px">${fmtPct(bk.avg)}</div><div class="lbl">when broke</div></div>
        </div>
      </div>`);
  });
}

function renderVerdict() {
  const W = META.ret_bars[state.h];
  const parts = META.cats.map((c) => {
    const s = cat(c), all = stat(s, state.h).avg, rp = revPct(s);
    const bk = stat(s.filter((r) => !r.rev), state.h).avg, rv = stat(s.filter((r) => r.rev), state.h).avg;
    if (c.startsWith("Support")) {
      return `<b>${c}:</b> ${rp.toFixed(0)}% bounce; bounces run <b>${fmtPct(rv)}</b> vs break-downs <b>${fmtPct(bk)}</b> at ${W} candles → net <b>${fmtPct(all)}</b> ` +
        `(${all >= 0 ? "positive edge for buying the bounce — small losses, big wins" : "the asymmetry doesn't pay here"}).`;
    }
    return `<b>${c}:</b> only ${rp.toFixed(0)}% reject; the rest break out and run <b>${fmtPct(bk)}</b> at ${W} candles → net price <b>${fmtPct(all)}</b> ` +
      `(${all >= 0 ? "price drifts UP — weak as a short" : "rejections dominate"}).`;
  });
  document.getElementById("p1-verdict").innerHTML = parts.join("<br><br>");
}

function renderP2() {
  const rb = META.ret_bars;
  let h = `<thead><tr><th class="l">Setup / outcome</th><th>n</th><th>%</th>` +
    rb.map((k) => `<th>Δ@${k}</th>`).join("") + `</tr></thead><tbody>`;
  META.cats.forEach((c) => {
    const s = cat(c);
    h += `<tr class="grp"><td class="l">${c}</td><td>${s.length.toLocaleString("en-IN")}</td><td></td>` + rb.map(() => "<td></td>").join("") + "</tr>";
    const brkLbl = c.startsWith("Support") ? "broke down" : "broke out";
    [["reversed", s.filter((r) => r.rev)], [brkLbl, s.filter((r) => !r.rev)], ["all", s]].forEach(([lab, rows]) => {
      const pct = lab === "all" ? "" : (100 * rows.length / s.length).toFixed(0) + "%";
      const cells = rb.map((k, i) => { const st = stat(rows, i); return `<td class="${clsSign(st.avg)}">${fmtPct(st.avg)} <span class="med">${fmtPct(st.med)}</span></td>`; }).join("");
      h += `<tr class="sub ${rows.length < 100 ? "thin" : ""}"><td class="l">${lab}</td><td>${rows.length.toLocaleString("en-IN")}</td><td>${pct}</td>${cells}</tr>`;
    });
  });
  document.getElementById("p2-table").innerHTML = h + "</tbody>";
}

function renderP3() {
  const wrap = document.getElementById("p3-wrap"); wrap.innerHTML = "";
  const W = META.ret_bars[state.h];
  META.cats.forEach((c) => {
    const s = cat(c);
    let h = `<div><div style="font-family:var(--mono);font-size:12px;color:var(--ink-muted);margin-bottom:6px">${c}</div>` +
      `<table class="bt-table"><thead><tr><th class="l">CONF band</th><th>n</th><th>rev%</th><th>Δ@${W}</th></tr></thead><tbody>`;
    META.bands.forEach(([lab, lo, hi]) => {
      const b = s.filter((r) => r.c >= lo && r.c < hi), st = stat(b, state.h), rp = revPct(b);
      h += `<tr class="p3row ${b.length && b.length < 100 ? "thin" : ""}" data-c="${c}" data-lo="${lo}" data-hi="${hi}" style="cursor:pointer">` +
        `<td class="l">${lab}</td><td>${b.length.toLocaleString("en-IN")}</td><td>${rp == null ? "—" : rp.toFixed(0) + "%"}</td><td class="${clsSign(st.avg)}">${fmtPct(st.avg)}</td></tr>`;
    });
    wrap.insertAdjacentHTML("beforeend", h + "</tbody></table></div>");
  });
  wrap.querySelectorAll(".p3row").forEach((tr) => tr.addEventListener("click", () => {
    const c = tr.dataset.c, lo = +tr.dataset.lo, hi = +tr.dataset.hi;
    setDrill(`${c} · CONF ${tr.querySelector("td").textContent}`, ROWS.filter((r) => r.su === c && r.c >= lo && r.c < hi));
  }));
}

function renderP4() {
  const W = META.ret_bars[state.h], slices = [];
  const add = (dim, slc, rows) => { if (rows.length) slices.push({ dim, slc, rows }); };
  ["1d", "1w", "1m"].forEach((tf) => add("Timeframe", tf.toUpperCase(), ROWS.filter((r) => r.tf === tf)));
  META.cats.forEach((c) => add("Setup", c, cat(c)));
  add("Line", "trend", ROWS.filter((r) => r.lt === "trendline"));
  add("Line", "horiz", ROWS.filter((r) => r.lt === "horizontal"));
  TOUCH_BANDS.forEach(([lab, lo, hi]) => add("Touches", lab, ROWS.filter((r) => r.tc >= lo && r.tc < hi)));
  let h = `<thead><tr><th class="l">Dimension</th><th class="l">Slice</th><th>rev%</th><th>Δ@${W}</th><th>n</th></tr></thead><tbody>`;
  slices.forEach((s, i) => {
    const st = stat(s.rows, state.h), rp = revPct(s.rows);
    h += `<tr class="p4row ${s.rows.length < 100 ? "thin" : ""}" data-i="${i}" style="cursor:pointer">` +
      `<td class="l dimc">${s.dim}</td><td class="l">${s.slc}</td><td>${rp == null ? "—" : rp.toFixed(0) + "%"}</td>` +
      `<td class="${clsSign(st.avg)}">${fmtPct(st.avg)}</td><td>${s.rows.length.toLocaleString("en-IN")}</td></tr>`;
  });
  const t = document.getElementById("p4-table"); t.innerHTML = h + "</tbody>";
  t.querySelectorAll(".p4row").forEach((tr) => tr.addEventListener("click", () => {
    const s = slices[+tr.dataset.i]; setDrill(`${s.dim} · ${s.slc}`, s.rows);
  }));
}

function renderCov() {
  const thin = [...cat("Support Reversal"), ...cat("Resistance Reversal")];
  document.getElementById("cov-body").innerHTML =
    `<b>${META.n.toLocaleString("en-IN")}</b> setups, <b>${META.dmin} → ${META.dmax}</b>, all walk-forward ` +
    `(each line built only from data available at its as-of date — no lookahead). Outcome: a close &gt; ` +
    `<b>${META.break_buffer_atr} ATR</b> past the line within <b>${META.classify_window}</b> candles = broke, else reversed. ` +
    `Returns are signed close-to-close %. Sample size <b>n</b> is on every number; anything with <b>n&lt;100</b> is dimmed ` +
    `— a big move on a thin slice isn't trustworthy. v1 covers reversal setups only.`;
}

/* ---- drill-down ---- */
const keyOf = (r) => `${r.sym}:${r.tf}:${r.dt}:${r.vn}`;

function makeChart() {
  const el = document.getElementById("p5-chart");
  p5chart = LC.createChart(el, {
    layout: { background: { type: "solid", color: "#0b0e13" }, textColor: "#8a95a3", fontFamily: "ui-monospace, monospace", fontSize: 11 },
    grid: { vertLines: { color: "#141a22" }, horzLines: { color: "#141a22" } },
    rightPriceScale: { borderColor: "#232b36" }, timeScale: { borderColor: "#232b36" },
    width: el.clientWidth || 600, height: 340,
  });
  new ResizeObserver(() => p5chart.applyOptions({ width: el.clientWidth })).observe(el);
}

function setDrill(label, rows) { DRILL = { label, rows: rows.slice() }; p5sel = null; renderDrill(); document.getElementById("p5").scrollIntoView({ behavior: "smooth", block: "nearest" }); }

function renderDrill() {
  const rows = DRILL.rows.slice().sort((a, b) => b.c - a.c), CAP = 300, shown = rows.slice(0, CAP);
  document.getElementById("p5-hint").style.display = "none";
  document.getElementById("p5-table").style.display = "";
  document.querySelector("#p5 h2").textContent =
    `Drill-down — ${DRILL.label} · ${rows.length.toLocaleString("en-IN")} setups${rows.length > CAP ? " (top 300 by CONF)" : ""}`;
  const hi = state.h;
  document.getElementById("p5-body").innerHTML = shown.map((r) =>
    `<tr class="${keyOf(r) === p5sel ? "sel" : ""}"><td class="l">${r.sym.replace("-EQ", "")}</td><td class="l">${r.dt}</td>` +
    `<td>${Math.round(r.c)}</td><td class="${r.rev ? "up" : "down"}">${r.rev ? "REVERSED" : "BROKE"}</td>` +
    `<td class="${clsSign(r.rets[r.rets.length - 1])}">${fmtPct(r.rets[r.rets.length - 1])}</td></tr>`).join("");
  document.querySelectorAll("#p5-body tr").forEach((tr, i) => tr.addEventListener("click", () => drawInstance(shown[i])));
}

async function drawInstance(r) {
  p5sel = keyOf(r); renderDrill();
  const candles = await (await fetch(`data/ohlcv/${safeName(r.sym)}__${r.tf}.json`)).json();
  const fwd = Math.max(...META.ret_bars, META.classify_window);
  const a = Math.max(0, r.fi - 20), z = Math.min(candles.length - 1, r.li + fwd + 5);
  if (p5main) p5chart.removeSeries(p5main);
  if (p5line) p5chart.removeSeries(p5line);
  p5main = p5chart.addCandlestickSeries({ upColor: "#2ea06a", downColor: "#e0554e", wickUpColor: "#2ea06a", wickDownColor: "#e0554e", borderVisible: false, priceLineVisible: false });
  p5main.setData(candles.slice(a, z + 1));
  const lv = (i) => r.vn + r.sl * (i - r.li), endI = Math.min(candles.length - 1, r.li + fwd);
  p5line = p5chart.addLineSeries({ color: "#e6edf3", lineWidth: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
  p5line.setData([{ time: candles[r.fi].time, value: lv(r.fi) }, { time: candles[endI].time, value: lv(endI) }]);
  p5main.setMarkers([{ time: candles[r.li].time, position: "aboveBar", color: "#e6b422", shape: "arrowDown", text: "as-of" }]);
  p5chart.applyOptions({ width: document.getElementById("p5-chart").clientWidth });
  p5chart.timeScale().fitContent();
  document.getElementById("p5-chart-hdr").innerHTML =
    `<b>${r.sym.replace("-EQ", "")}</b> ${r.tf} · ${r.su} · CONF <b>${Math.round(r.c)}</b> · as-of <b>${r.dt}</b> · ` +
    `<span class="${r.rev ? "up" : "down"}">${r.rev ? "REVERSED" : "BROKE"}</span> · move @${META.ret_bars.join("/")}: ` +
    META.ret_bars.map((k, i) => `<span class="${clsSign(r.rets[i])}">${fmtPct(r.rets[i])}</span>`).join(" / ") +
    ` · white line = S/R line, ↓ = as-of`;
}

window.addEventListener("DOMContentLoaded", load);
