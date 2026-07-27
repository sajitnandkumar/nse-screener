"""
Render hull-detected lines for a small sample of symbols to ONE self-contained
HTML page, so the lines can be eyeballed before scaling. Reads the local DB only.

Usage:  ./venv/bin/python verify_hull.py    ->  writes hull_verify.html
Open hull_verify.html in a browser. Each detected line gets its own candlestick
chart with the line extended to now, its two ANCHORS marked large ('A') and every
TOUCH marked small. A correct line sits on the closes with nothing poking through
between the anchors.
"""

import json
import os

import db
from hull_lines import detect_hull_lines
from resample import to_weekly, to_monthly

SAMPLE = ["RELIANCE", "HDFCBANK", "INDUSINDBK", "JAMNAAUTO", "INDIAGLYCO",
          "ELGIEQUIP", "SUNTV", "GOKULAGRO", "DBCORP", "PERSISTENT"]
TFS = [("1d", None), ("1w", to_weekly), ("1m", to_monthly)]
PAD = 15                          # bars of context before the first anchor
VENDOR = os.path.join("static", "vendor", "lightweight-charts.standalone.production.js")
OUT = "hull_verify.html"


def _chart_spec(symbol, tf, rows, ln, cid):
    """Build the JSON a single chart needs (candles slice + line + markers)."""
    a0 = max(0, ln["first_anchor_idx"] - PAD)
    view = rows[a0:]
    candles = [{"time": r[0][:10], "open": r[1], "high": r[2],
                "low": r[3], "close": r[4]} for r in view]

    # Line: from the first anchor (on the line) to now (value_now), extended straight.
    line = [
        {"time": ln["anchor_points"][0]["date"], "value": ln["anchor_points"][0]["price"]},
        {"time": rows[ln["last_idx"]][0][:10], "value": ln["value_now"]},
    ]
    anchor_dates = {p["date"] for p in ln["anchor_points"]}
    pos = "belowBar" if ln["side"] == "support" else "aboveBar"
    markers = []
    for tp in ln["touch_points"]:
        is_anchor = tp["date"] in anchor_dates
        markers.append({"time": tp["date"], "position": pos,
                        "color": "#e6b422" if is_anchor else "#8a95a3",
                        "shape": "circle", "size": 2 if is_anchor else 1,
                        "text": "A" if is_anchor else ""})
    markers.sort(key=lambda m: m["time"])

    title = (f"{symbol}  ·  {tf}  ·  {ln['side'].upper()} {ln['line_type']}  ·  "
             f"{ln['touch_count']} touches  ·  anchors {ln['anchor_points'][0]['date']} "
             f"→ {ln['anchor_points'][1]['date']}  ·  last touch {ln['last_touch_date']}  ·  "
             f"value_now {ln['value_now']}  ·  dist {ln['dist_now_atr']} ATR")
    return {"id": cid, "title": title, "side": ln["side"],
            "candles": candles, "line": line, "markers": markers}


def main():
    charts, coverage = [], []
    for symbol in SAMPLE:
        sym = symbol + "-EQ"
        daily = db.read_candles(sym)
        if not daily:
            coverage.append(f"{symbol}: NO DATA in DB")
            continue
        for tf, resample in TFS:
            rows = resample(daily) if resample else daily
            lines = detect_hull_lines(rows, tf)
            coverage.append(f"{symbol} {tf}: {len(lines)} line(s)")
            for ln in sorted(lines, key=lambda l: -l["touch_count"]):
                charts.append(_chart_spec(symbol, tf, rows, ln, f"c{len(charts)}"))

    with open(VENDOR) as f:
        vendor_js = f.read()

    html = _TEMPLATE.replace("/*VENDOR*/", vendor_js) \
                    .replace("/*CHARTS*/", json.dumps(charts)) \
                    .replace("<!--COVERAGE-->", "<br>".join(coverage))
    with open(OUT, "w") as f:
        f.write(html)
    print(f"Wrote {OUT}: {len(charts)} charts from {len(SAMPLE)} symbols.")
    print("\n".join(coverage))


_TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Hull line verification</title>
<style>
  body{background:#0b0e13;color:#d6dee8;font-family:ui-monospace,Menlo,monospace;margin:0;padding:16px}
  h1{font-size:14px;color:#8a95a3;letter-spacing:.1em;text-transform:uppercase}
  .cov{color:#5b6570;font-size:11px;line-height:1.6;margin:8px 0 24px}
  .card{margin:0 0 26px}
  .cap{font-size:12px;color:#d6dee8;margin:0 0 6px}
  .chart{width:100%;height:340px;border:1px solid #232b36}
</style></head><body>
<h1>Hull line verification</h1>
<div class="cov"><!--COVERAGE--></div>
<div id="root"></div>
<script>/*VENDOR*/</script>
<script>
const LC = LightweightCharts;
const CHARTS = /*CHARTS*/;
const root = document.getElementById("root");
CHARTS.forEach(spec => {
  const card = document.createElement("div"); card.className = "card";
  const cap = document.createElement("div"); cap.className = "cap"; cap.textContent = spec.title;
  const div = document.createElement("div"); div.className = "chart";
  card.appendChild(cap); card.appendChild(div); root.appendChild(card);
  const chart = LC.createChart(div, {
    layout:{background:{type:"solid",color:"#0b0e13"},textColor:"#8a95a3",fontFamily:"ui-monospace,monospace",fontSize:11},
    grid:{vertLines:{color:"#141a22"},horzLines:{color:"#141a22"}},
    rightPriceScale:{borderColor:"#232b36"}, timeScale:{borderColor:"#232b36"},
    width: div.clientWidth, height: 340,
  });
  const cs = chart.addCandlestickSeries({upColor:"#2ea06a",downColor:"#e0554e",wickUpColor:"#2ea06a",wickDownColor:"#e0554e",borderVisible:false,priceLineVisible:false,lastValueVisible:false});
  cs.setData(spec.candles);
  const ls = chart.addLineSeries({color: spec.side==="support" ? "#38bdf8" : "#f59e42", lineWidth:2, priceLineVisible:false, lastValueVisible:false, crosshairMarkerVisible:false});
  ls.setData(spec.line);
  cs.setMarkers(spec.markers);
  chart.timeScale().fitContent();
});
</script>
</body></html>"""


if __name__ == "__main__":
    main()
