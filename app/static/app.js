// ===== Trading AI dashboard =====
// Loads /api/dashboard for the chosen stock and draws the cards, chart and table.

const SYMBOLS = [
  { id: "NSE:RELIANCE-EQ", label: "RELIANCE" },
  { id: "NSE:TCS-EQ", label: "TCS" },
  { id: "NSE:INFY-EQ", label: "INFY" },
  { id: "NSE:HDFCBANK-EQ", label: "HDFCBANK" },
  { id: "NSE:SBIN-EQ", label: "SBIN" },
];

const IST_OFFSET = 5.5 * 3600;   // chart library shows UTC; shift to Indian time
const COLORS = { up: "#1fbf75", down: "#ef4f5a", ma10: "#3987e5", ma20: "#d95926" };

let symbol = SYMBOLS[0].id;
let chart, candleSeries, volumeSeries, ma10Series, ma20Series;
let candlesByTime = new Map();

const $ = (id) => document.getElementById(id);
const fmt = (n, d = 2) => n.toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d });
const pct = (n) => `${n >= 0 ? "+" : ""}${(n * 100).toFixed(2)}%`;
const timeStr = (t) => new Date(t * 1000).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Kolkata" });

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

// ---------- Chart ----------
function createChart() {
  chart = LightweightCharts.createChart($("chart"), {
    autoSize: true,
    layout: { background: { color: "transparent" }, textColor: "#8a93a6", fontFamily: "Inter, system-ui, sans-serif" },
    grid: { vertLines: { color: "rgba(33,40,54,.45)" }, horzLines: { color: "rgba(33,40,54,.45)" } },
    rightPriceScale: { borderColor: "#212836" },
    timeScale: { borderColor: "#212836", timeVisible: true, secondsVisible: false },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
  });

  volumeSeries = chart.addHistogramSeries({ priceScaleId: "", priceFormat: { type: "volume" }, lastValueVisible: false, priceLineVisible: false });
  volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });

  candleSeries = chart.addCandlestickSeries({
    upColor: COLORS.up, downColor: COLORS.down, borderVisible: false,
    wickUpColor: COLORS.up, wickDownColor: COLORS.down,
  });
  candleSeries.priceScale().applyOptions({ scaleMargins: { top: 0.08, bottom: 0.22 } });

  const lineOpts = { lineWidth: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false };
  ma10Series = chart.addLineSeries({ ...lineOpts, color: COLORS.ma10 });
  ma20Series = chart.addLineSeries({ ...lineOpts, color: COLORS.ma20 });

  // Hover: show that candle's numbers above the chart
  chart.subscribeCrosshairMove((p) => {
    const c = p.time ? candlesByTime.get(p.time) : null;
    showOhlc(c || [...candlesByTime.values()].at(-1));
  });
}

function showOhlc(c) {
  if (!c) return;
  const cls = c.close >= c.open ? "up" : "down";
  $("ohlc").innerHTML =
    `<span>${timeStr(c.time)}</span>` +
    `<span>O <b>${fmt(c.open)}</b></span><span>H <b>${fmt(c.high)}</b></span>` +
    `<span>L <b>${fmt(c.low)}</b></span><span>C <b class="${cls}">${fmt(c.close)}</b></span>` +
    `<span>MA10 <b>${fmt(c.ma_10)}</b></span><span>MA20 <b>${fmt(c.ma_20)}</b></span>`;
}

function drawChart(candles) {
  const t = (c) => c.time + IST_OFFSET;
  candlesByTime = new Map(candles.map((c) => [t(c), c]));

  candleSeries.setData(candles.map((c) => ({ time: t(c), open: c.open, high: c.high, low: c.low, close: c.close })));
  volumeSeries.setData(candles.map((c) => ({
    time: t(c), value: c.volume,
    color: c.close >= c.open ? "rgba(31,191,117,.28)" : "rgba(239,79,90,.28)",
  })));
  ma10Series.setData(candles.map((c) => ({ time: t(c), value: c.ma_10 })));
  ma20Series.setData(candles.map((c) => ({ time: t(c), value: c.ma_20 })));

  // Arrows only where the rule signal CHANGES to buy or sell (keeps chart clean)
  const markers = [];
  for (let i = 1; i < candles.length; i++) {
    const s = candles[i].signal;
    if (s === candles[i - 1].signal || s === 0) continue;
    markers.push(s === 1
      ? { time: t(candles[i]), position: "belowBar", color: COLORS.up, shape: "arrowUp" }
      : { time: t(candles[i]), position: "aboveBar", color: COLORS.down, shape: "arrowDown" });
  }
  candleSeries.setMarkers(markers);

  // Show roughly the last 150 candles; scroll/zoom to see more
  chart.timeScale().setVisibleLogicalRange({ from: candles.length - 150, to: candles.length + 3 });
  showOhlc(candles.at(-1));
}

// ---------- Cards ----------
const SIGNAL = {
  1: { text: "BUY", cls: "up", icon: "▲", why: "Price above MA 10, MA 10 above MA 20" },
  "-1": { text: "SELL", cls: "down", icon: "▼", why: "Price below MA 10, MA 10 below MA 20" },
  0: { text: "HOLD", cls: "hold", icon: "■", why: "No clear trend right now" },
};

function drawCards(data) {
  const candles = data.candles;
  const last = candles.at(-1);

  // Change since the first candle of the latest trading day
  const day = new Date((last.time + IST_OFFSET) * 1000).toISOString().slice(0, 10);
  const dayOpen = candles.find((c) => new Date((c.time + IST_OFFSET) * 1000).toISOString().slice(0, 10) === day).open;
  const change = last.close / dayOpen - 1;
  $("lastPrice").textContent = `₹${fmt(last.close)}`;
  $("priceChange").innerHTML = `<span class="${change >= 0 ? "up" : "down"}">${change >= 0 ? "▲" : "▼"} ${pct(change)}</span> today`;

  const s = SIGNAL[last.signal];
  $("ruleSignal").innerHTML = `<span class="signal-chip ${s.cls}"><span>${s.icon}</span>${s.text}</span>`;
  $("ruleReason").textContent = s.why;

  if (data.ai) {
    const up = data.ai.prediction === "UP";
    const prob = data.ai.probability_up;
    $("aiPrediction").innerHTML = `<span class="signal-chip ${up ? "up" : "down"}"><span>${up ? "▲" : "▼"}</span>${data.ai.prediction}</span>`;
    $("aiMeter").style.width = `${prob * 100}%`;
    $("aiProb").innerHTML = `Chance of going up: <b class="${up ? "up" : "down"}">${(prob * 100).toFixed(1)}%</b>`;
  } else {
    $("aiPrediction").innerHTML = `<span class="muted" style="font-size:20px">Not trained</span>`;
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

function drawModelPanel(m) {
  if (!$("trainBtn").disabled) $("trainBtn").querySelector(".btn-label").textContent = m ? "Retrain model" : "Train model";
  if (!m) {
    $("modelMeta").textContent = "Not trained yet. Training takes a few seconds.";
    $("importance").innerHTML = `<p class="muted small">Train the model to see which features matter most.</p>`;
    return;
  }
  const label = SYMBOLS.find((s) => s.id === m.symbol)?.label || m.symbol || "—";
  $("modelMeta").innerHTML = `Trained on <b>${label}</b> · ${m.train_rows} candles<br>Tested on ${m.test_rows} unseen candles · ${m.trained_at}`;

  const entries = Object.entries(m.feature_importance).sort((a, b) => b[1] - a[1]);
  const max = entries[0][1];
  $("importance").innerHTML = entries.map(([name, v]) => `
    <div class="imp-row">
      <span class="name">${name}</span>
      <span class="bar"><i data-w="${(v / max) * 100}"></i></span>
      <span class="val mono">${(v * 100).toFixed(0)}%</span>
    </div>`).join("");
  // animate bars in
  requestAnimationFrame(() => $("importance").querySelectorAll("i").forEach((i) => (i.style.width = i.dataset.w + "%")));
}

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
      <td>${(c.volatility * 100).toFixed(3)}%</td>
      <td>${Math.round(c.volume).toLocaleString("en-IN")}</td>
      <td><span class="tag ${s.cls} ${s.cls}">${s.text}</span></td>
    </tr>`;
  }).join("");
}

function drawSource(src) {
  const badge = $("sourceBadge");
  badge.className = `badge ${src.type}`;
  $("sourceText").textContent = src.type === "live" ? "Live · Fyers" : "Demo data";
  badge.title = src.type === "live" ? "Real market data from Fyers" : `Fyers not connected: ${src.detail}`;
}

// ---------- Loading ----------
async function load() {
  document.body.classList.add("loading");
  $("refreshBtn").classList.add("spinning");
  try {
    const res = await fetch(`/api/dashboard?symbol=${encodeURIComponent(symbol)}`);
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    const data = await res.json();

    const label = SYMBOLS.find((s) => s.id === symbol).label;
    $("chartTitle").textContent = `${label} · 5-minute`;
    drawSource(data.source);
    drawChart(data.candles);
    drawCards(data);
    drawModelPanel(data.model);
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
  btn.querySelector(".btn-label").textContent = "Training…";
  btn.querySelector(".spinner").hidden = false;
  try {
    const res = await fetch(`/train?symbol=${encodeURIComponent(symbol)}`, { method: "POST" });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    const m = await res.json();
    toast(`Model trained — ${(m.test_accuracy * 100).toFixed(1)}% accuracy on unseen data`);
    await load();
  } catch (e) {
    toast(`Training failed: ${e.message}`, true);
  } finally {
    btn.disabled = false;
    btn.querySelector(".btn-label").textContent = "Retrain model";
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
  toastTimer = setTimeout(() => (t.hidden = true), 3500);
}

// ---------- Start ----------
renderSymbols();
createChart();
$("refreshBtn").addEventListener("click", load);
$("trainBtn").addEventListener("click", train);
load();
setInterval(load, 60_000);   // refresh every minute
