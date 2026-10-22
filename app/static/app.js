// ===== Trading AI dashboard =====
// Loads /api/dashboard for the chosen stock and draws the cards, charts and tables.

const SYMBOLS = [
  { id: "NSE:RELIANCE-EQ", label: "RELIANCE" },
  { id: "NSE:TCS-EQ", label: "TCS" },
  { id: "NSE:INFY-EQ", label: "INFY" },
  { id: "NSE:HDFCBANK-EQ", label: "HDFCBANK" },
  { id: "NSE:SBIN-EQ", label: "SBIN" },
];

const IST_OFFSET = 5.5 * 3600;   // chart library shows UTC; shift to Indian time
const COLORS = {
  up: "#1fbf75", down: "#ef4f5a", ma10: "#3987e5", ma20: "#d95926",
  bb: "rgba(138,147,166,.7)", rsi: "#9085e9", ai: "#3987e5", rules: "#d95926", hold: "#8a93a6",
};
const CHART_BASE = {
  autoSize: true,
  layout: { background: { color: "transparent" }, textColor: "#8a93a6", fontFamily: "Inter, system-ui, sans-serif" },
  grid: { vertLines: { color: "rgba(33,40,54,.45)" }, horzLines: { color: "rgba(33,40,54,.45)" } },
  rightPriceScale: { borderColor: "#212836", minimumWidth: 72 },
  timeScale: { borderColor: "#212836", timeVisible: true, secondsVisible: false },
  crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
};

let symbol = SYMBOLS[0].id;
let chart, candleSeries, volumeSeries, ma10Series, ma20Series, bbUpper, bbLower;
let rsiChart, rsiSeries, equityChart, equitySeries = {};
let candlesByTime = new Map(), equityByTime = new Map();

const $ = (id) => document.getElementById(id);
const fmt = (n, d = 2) => n.toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d });
const pct = (n, d = 2) => `${n >= 0 ? "+" : ""}${(n * 100).toFixed(d)}%`;
const timeStr = (t) => new Date(t * 1000).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Kolkata" });
const dateStr = (t) => new Date(t * 1000).toLocaleDateString("en-IN", { day: "numeric", month: "short", timeZone: "Asia/Kolkata" });
const ist = (t) => t + IST_OFFSET;
const labelOf = (id) => SYMBOLS.find((s) => s.id === id)?.label || id;

// ---------- Symbol buttons ----------
function renderSymbols() {
  $("symbols").innerHTML = SYMBOLS.map((s) =>
    `<button data-id="${s.id}" class="${s.id === symbol ? "active" : ""}">${s.label}</button>`
  ).join("");
  $("symbols").querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", () => {
      symbol = b.dataset.id;
      renderSymbols();
      load();
    })
  );
}

// ---------- Charts ----------
function createCharts() {
  // Price chart
  chart = LightweightCharts.createChart($("chart"), CHART_BASE);
  volumeSeries = chart.addHistogramSeries({ priceScaleId: "", priceFormat: { type: "volume" }, lastValueVisible: false, priceLineVisible: false });
  volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
  candleSeries = chart.addCandlestickSeries({
    upColor: COLORS.up, downColor: COLORS.down, borderVisible: false,
    wickUpColor: COLORS.up, wickDownColor: COLORS.down,
  });
  candleSeries.priceScale().applyOptions({ scaleMargins: { top: 0.08, bottom: 0.22 } });

  const line = { lineWidth: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false };
  ma10Series = chart.addLineSeries({ ...line, color: COLORS.ma10 });
  ma20Series = chart.addLineSeries({ ...line, color: COLORS.ma20 });
  const bb = { ...line, lineWidth: 1, color: COLORS.bb, lineStyle: LightweightCharts.LineStyle.Dashed, visible: false };
  bbUpper = chart.addLineSeries(bb);
  bbLower = chart.addLineSeries(bb);

  // RSI chart, kept in sync with the price chart when you scroll/zoom
  rsiChart = LightweightCharts.createChart($("rsiChart"), {
    ...CHART_BASE, timeScale: { ...CHART_BASE.timeScale, visible: false },
    handleScroll: false, handleScale: false,
  });
  rsiSeries = rsiChart.addLineSeries({ ...line, color: COLORS.rsi, lastValueVisible: true });
  rsiSeries.applyOptions({ autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }) });
  rsiSeries.priceScale().applyOptions({ scaleMargins: { top: 0.06, bottom: 0.06 } });
  for (const level of [70, 30]) {
    rsiSeries.createPriceLine({ price: level, color: "rgba(138,147,166,.5)", lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed, axisLabelVisible: false });
  }
  chart.timeScale().subscribeVisibleLogicalRangeChange((r) => r && rsiChart.timeScale().setVisibleLogicalRange(r));

  // Hover: show that candle's numbers above the chart
  chart.subscribeCrosshairMove((p) => {
    const c = p.time ? candlesByTime.get(p.time) : null;
    showOhlc(c || [...candlesByTime.values()].at(-1));
  });

  // Equity curve chart (backtest)
  equityChart = LightweightCharts.createChart($("equityChart"), {
    ...CHART_BASE, localization: { priceFormatter: (v) => `${v >= 0 ? "+" : ""}${v.toFixed(2)}%` },
  });
  const eq = { lineWidth: 2, priceLineVisible: false, lastValueVisible: true };
  equitySeries.buy_hold = equityChart.addLineSeries({ ...eq, color: COLORS.hold, lineStyle: LightweightCharts.LineStyle.Dashed });
  equitySeries.rules = equityChart.addLineSeries({ ...eq, color: COLORS.rules });
  equitySeries.ai = equityChart.addLineSeries({ ...eq, color: COLORS.ai });
  equityChart.subscribeCrosshairMove((p) => {
    const e = p.time ? equityByTime.get(p.time) : null;
    showEquity(e || [...equityByTime.values()].at(-1));
  });

  // Overlay toggles (MA / Bollinger)
  document.querySelectorAll(".chip[data-overlay]").forEach((chip) =>
    chip.addEventListener("click", () => {
      const on = chip.classList.toggle("on");
      const series = chip.dataset.overlay === "ma" ? [ma10Series, ma20Series] : [bbUpper, bbLower];
      series.forEach((s) => s.applyOptions({ visible: on }));
    })
  );
}

function showOhlc(c) {
  if (!c) return;
  const cls = c.close >= c.open ? "up" : "down";
  $("ohlc").innerHTML =
    `<span>${dateStr(c.time)} ${timeStr(c.time)}</span>` +
    `<span>O <b>${fmt(c.open)}</b></span><span>H <b>${fmt(c.high)}</b></span>` +
    `<span>L <b>${fmt(c.low)}</b></span><span>C <b class="${cls}">${fmt(c.close)}</b></span>` +
    `<span>MA10 <b>${fmt(c.ma_10)}</b></span><span>MA20 <b>${fmt(c.ma_20)}</b></span>`;
  $("rsiValue").textContent = c.rsi.toFixed(1);
}

function drawPriceChart(candles) {
  candlesByTime = new Map(candles.map((c) => [ist(c.time), c]));
  const pts = (key) => candles.map((c) => ({ time: ist(c.time), value: c[key] }));

  candleSeries.setData(candles.map((c) => ({ time: ist(c.time), open: c.open, high: c.high, low: c.low, close: c.close })));
  volumeSeries.setData(candles.map((c) => ({
    time: ist(c.time), value: c.volume,
    color: c.close >= c.open ? "rgba(31,191,117,.28)" : "rgba(239,79,90,.28)",
  })));
  ma10Series.setData(pts("ma_10"));
  ma20Series.setData(pts("ma_20"));
  bbUpper.setData(pts("bb_upper"));
  bbLower.setData(pts("bb_lower"));
  rsiSeries.setData(pts("rsi"));

  // Arrows only where the rule signal CHANGES to buy or sell (keeps chart clean)
  const markers = [];
  for (let i = 1; i < candles.length; i++) {
    const s = candles[i].signal;
    if (s === candles[i - 1].signal || s === 0) continue;
    markers.push(s === 1
      ? { time: ist(candles[i].time), position: "belowBar", color: COLORS.up, shape: "arrowUp" }
      : { time: ist(candles[i].time), position: "aboveBar", color: COLORS.down, shape: "arrowDown" });
  }
  candleSeries.setMarkers(markers);

  // Show roughly the last 150 candles; scroll/zoom to see more
  chart.timeScale().setVisibleLogicalRange({ from: candles.length - 150, to: candles.length + 3 });
  showOhlc(candles.at(-1));
}

// ---------- KPI cards ----------
const SIGNAL = {
  1: { text: "BUY", cls: "up", icon: "▲", why: "Price above MA 10, MA 10 above MA 20" },
  "-1": { text: "SELL", cls: "down", icon: "▼", why: "Price below MA 10, MA 10 below MA 20" },
  0: { text: "HOLD", cls: "hold", icon: "■", why: "No clear trend right now" },
};
const ACTION = { BUY: SIGNAL[1], SELL: SIGNAL[-1], HOLD: SIGNAL[0] };

function drawCards(data) {
  const candles = data.candles;
  const last = candles.at(-1);

  // Change since the first candle of the latest trading day
  const dayOf = (c) => new Date(ist(c.time) * 1000).toISOString().slice(0, 10);
  const dayOpen = candles.find((c) => dayOf(c) === dayOf(last)).open;
  const change = last.close / dayOpen - 1;
  $("lastPrice").textContent = `₹${fmt(last.close)}`;
  $("priceChange").innerHTML = `<span class="${change >= 0 ? "up" : "down"}">${change >= 0 ? "▲" : "▼"} ${pct(change)}</span> today`;

  const s = SIGNAL[last.signal];
  $("ruleSignal").innerHTML = `<span class="signal-chip ${s.cls}"><span>${s.icon}</span>${s.text}</span>`;
  $("ruleReason").textContent = s.why;

  if (data.ai) {
    const a = ACTION[data.ai.action];
    const prob = data.ai.probability_up;
    $("aiPrediction").innerHTML = `<span class="signal-chip ${a.cls}"><span>${a.icon}</span>${a.text}</span>`;
    $("aiModelName").textContent = data.ai.model;
    $("aiMeter").style.width = `${prob * 100}%`;
    $("aiProb").innerHTML = `Chance next candle is up: <b class="${prob >= 0.5 ? "up" : "down"}">${(prob * 100).toFixed(1)}%</b>`;
  } else {
    $("aiPrediction").innerHTML = `<span class="muted" style="font-size:20px">Not trained</span>`;
    $("aiModelName").textContent = "next 5-min candle";
    $("aiMeter").style.width = "50%";
    $("aiProb").textContent = "Click “Train model” to get predictions";
  }

  const m = data.model;
  if (m) {
    const edge = (m.test_accuracy - m.baseline) * 100;
    $("accuracy").textContent = `${(m.test_accuracy * 100).toFixed(1)}%`;
    $("accuracySub").innerHTML =
      `<span class="${edge >= 0 ? "up" : "down"}">${edge >= 0 ? "+" : ""}${edge.toFixed(1)} pts</span> vs naive guess (${(m.baseline * 100).toFixed(1)}%)`;
  } else {
    $("accuracy").textContent = "—";
    $("accuracySub").textContent = "Train the model to measure it";
  }
}

// ---------- Side panel ----------
function drawModelPanel(m) {
  if (!$("trainBtn").disabled) $("trainBtn").querySelector(".btn-label").textContent = m ? "Retrain models" : "Train models";
  if (!m) {
    $("bestModelPill").textContent = "5 models compete";
    $("modelMeta").textContent = "Not trained yet for this stock.";
    $("importance").innerHTML = `<p class="muted small">Train the model to see which features matter most.</p>`;
    return;
  }
  $("bestModelPill").textContent = `Winner: ${m.best_model}`;
  $("modelMeta").innerHTML =
    `Trained on <b>${labelOf(m.symbol)}</b> · ${m.train_rows.toLocaleString("en-IN")} candles · ${m.training_seconds}s<br>` +
    `Tested on ${m.test_rows} unseen candles · ${m.trained_at}`;

  // Permutation importance can be slightly negative (= feature didn't help) -> show as 0
  const entries = Object.entries(m.feature_importance).slice(0, 8);
  const max = Math.max(...entries.map(([, v]) => v), 1e-9);
  $("importance").innerHTML = entries.map(([name, v]) => `
    <div class="imp-row">
      <span class="name">${name}</span>
      <span class="bar"><i data-w="${Math.max(v, 0) / max * 100}"></i></span>
      <span class="val mono">${(v * 100).toFixed(1)}</span>
    </div>`).join("");
  requestAnimationFrame(() => $("importance").querySelectorAll("i").forEach((i) => (i.style.width = i.dataset.w + "%")));
}

// ---------- Backtest ----------
function showEquity(e) {
  if (!e) return;
  $("equityValues").innerHTML = `<span>${dateStr(e.time)} ${timeStr(e.time)}</span>` +
    [["AI", "ai"], ["Rules", "rules"], ["Buy & hold", "buy_hold"]]
      .map(([n, k]) => `<span>${n} <b class="${e[k] >= 1 ? "up" : "down"}">${pct(e[k] - 1)}</b></span>`).join("");
}

function drawBacktest(m) {
  if (!m) {
    Object.values(equitySeries).forEach((s) => s.setData([]));
    equityByTime = new Map();
    $("equityValues").innerHTML = "";
    $("backtestMeta").textContent = "Train the model to backtest it on data it has never seen.";
    $("statsBody").innerHTML = `<tr><td colspan="4" class="muted">—</td></tr>`;
    return;
  }
  const { stats, equity } = m.backtest;
  equityByTime = new Map(equity.map((e) => [ist(e.time), e]));
  for (const key of ["ai", "rules", "buy_hold"]) {
    equitySeries[key].setData(equity.map((e) => ({ time: ist(e.time), value: (e[key] - 1) * 100 })));
  }
  equityChart.timeScale().fitContent();
  showEquity(equity.at(-1));
  $("backtestMeta").textContent =
    `${m.best_model} on the last ${equity.length} candles it never trained on (${dateStr(equity[0].time)} – ${dateStr(equity.at(-1).time)}), incl. 0.03% cost per trade.`;

  const rows = [
    ["Total return", "total_return", (v) => `<span class="${v >= 0 ? "up" : "down"}">${pct(v)}</span>`],
    ["Sharpe ratio", "sharpe", (v) => v.toFixed(2)],
    ["Max drawdown", "max_drawdown", (v) => `<span class="down">${pct(v)}</span>`],
    ["Win rate", "win_rate", (v) => `${(v * 100).toFixed(1)}%`],
    ["Trades", "trades", (v) => v],
    ["Time in market", "exposure", (v) => `${(v * 100).toFixed(0)}%`],
  ];
  $("statsBody").innerHTML = rows.map(([label, key, f]) =>
    `<tr><td>${label}</td><td>${f(stats.ai[key])}</td><td>${f(stats.rules[key])}</td><td>${f(stats.buy_hold[key])}</td></tr>`
  ).join("");
}

// ---------- Model lab ----------
function drawLab(m) {
  if (!m) {
    $("modelsBody").innerHTML = `<tr><td colspan="6" class="muted">Train the model to compare.</td></tr>`;
    $("confusion").innerHTML = `<p class="muted small">—</p>`;
    $("tuning").innerHTML = `<p class="muted small">—</p>`;
    return;
  }
  const aucCell = (v) => `<span class="auc-cell">${v.toFixed(3)}<span class="auc-bar"><i style="width:${Math.max(0, (v - 0.4) / 0.2) * 100}%"></i></span></span>`;
  $("modelsBody").innerHTML = m.comparison.map((r) => `
    <tr class="${r.best ? "best" : ""}">
      <td>${r.name}</td>
      <td>${aucCell(r.cv.auc)}</td>
      <td>${r.holdout.auc.toFixed(3)}</td>
      <td>${(r.holdout.accuracy * 100).toFixed(1)}%</td>
      <td>${(r.holdout.precision * 100).toFixed(1)}%</td>
      <td>${(r.holdout.recall * 100).toFixed(1)}%</td>
    </tr>`).join("");

  // Confusion matrix: shade = share of all predictions
  const c = m.confusion, total = c.tn + c.fp + c.fn + c.tp;
  const cell = (n, label) => `<div class="cell" style="background:rgba(57,135,229,${(0.08 + 0.5 * n / total).toFixed(2)})"><b>${n}</b><span>${label}</span></div>`;
  $("confusion").innerHTML = `
    <span></span><span class="lbl">Predicted ▼</span><span class="lbl">Predicted ▲</span>
    <span class="lbl">Actual ▼</span>${cell(c.tn, "correct")}${cell(c.fp, "false alarm")}
    <span class="lbl">Actual ▲</span>${cell(c.fn, "missed")}${cell(c.tp, "correct")}
    <p class="confusion-note">Right ${(((c.tn + c.tp) / total) * 100).toFixed(1)}% of the time on ${total} unseen candles.</p>`;

  const t = m.tuning;
  $("tuning").innerHTML = `
    <div class="big">${t.best_auc.toFixed(3)}</div>
    <p class="muted small" style="margin:4px 0 0">best walk-forward AUC after ${t.trials} trials</p>
    <dl>${Object.entries(t.params).map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>`;
}

// ---------- Table ----------
function drawTable(candles) {
  const rows = candles.slice(-12).reverse();
  $("tableBody").innerHTML = rows.map((c) => {
    const s = SIGNAL[c.signal];
    return `<tr>
      <td>${timeStr(c.time)}</td>
      <td>${fmt(c.close)}</td>
      <td class="${c.returns >= 0 ? "up" : "down"}">${pct(c.returns)}</td>
      <td>${fmt(c.ma_10)}</td>
      <td>${fmt(c.ma_20)}</td>
      <td>${c.rsi.toFixed(1)}</td>
      <td>${(c.volatility * 100).toFixed(3)}%</td>
      <td>${Math.round(c.volume).toLocaleString("en-IN")}</td>
      <td><span class="tag ${s.cls}">${s.text}</span></td>
    </tr>`;
  }).join("");
}

function drawSource(src) {
  const badge = $("sourceBadge");
  const live = src.type === "live";
  badge.className = `badge ${src.type}`;
  $("sourceText").textContent = live ? "Live · Fyers" : "Demo data";
  badge.title = live ? "Real market data from Fyers" : `Fyers not connected: ${src.detail}`;
  $("connectBtn").hidden = live;
}

// ---------- Loading ----------
async function load() {
  document.body.classList.add("loading");
  $("refreshBtn").classList.add("spinning");
  try {
    const res = await fetch(`/api/dashboard?symbol=${encodeURIComponent(symbol)}`);
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    const data = await res.json();

    $("chartTitle").textContent = `${labelOf(symbol)} · 5-minute`;
    drawSource(data.source);
    drawPriceChart(data.candles);
    drawCards(data);
    drawModelPanel(data.model);
    drawBacktest(data.model);
    drawLab(data.model);
    drawTable(data.candles);
    $("updatedAt").textContent = `Updated ${new Date().toLocaleTimeString("en-IN")}`;
  } catch (e) {
    toast(`Could not load data: ${e.message}`, true);
  } finally {
    document.body.classList.remove("loading");
    $("refreshBtn").classList.remove("spinning");
  }
}

async function train() {
  const btn = $("trainBtn");
  btn.disabled = true;
  btn.querySelector(".btn-label").textContent = "Training 5 models…";
  btn.querySelector(".spinner").hidden = false;
  try {
    const res = await fetch(`/train?symbol=${encodeURIComponent(symbol)}`, { method: "POST" });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    const m = await res.json();
    toast(`${m.best_model} won — ${(m.test_accuracy * 100).toFixed(1)}% accuracy on unseen data`);
    await load();
  } catch (e) {
    toast(`Training failed: ${e.message}`, true);
  } finally {
    btn.disabled = false;
    btn.querySelector(".btn-label").textContent = "Retrain models";
    btn.querySelector(".spinner").hidden = true;
  }
}

let toastTimer;
function toast(msg, isError = false) {
  const t = $("toast");
  t.textContent = msg;
  t.className = `toast${isError ? " error" : ""}`;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), 4000);
}

// ---------- Start ----------
renderSymbols();
createCharts();
$("refreshBtn").addEventListener("click", load);
$("connectBtn").addEventListener("click", () => (location.href = "/fyers/login"));
if (new URLSearchParams(location.search).has("connected")) {
  toast("Fyers connected — loading live data");
  history.replaceState(null, "", "/");
}
$("trainBtn").addEventListener("click", train);
load();
setInterval(load, 60_000);   // refresh every minute
