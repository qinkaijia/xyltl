const PAGE_NAMES = ["overview", "monitor", "analysis", "operations"];

const state = {
  apiBase: defaultApiBase(),
  activePage: getInitialPage(),
  summary: null,
  devices: [],
  alarms: [],
  evaluateScenarios: {
    normal: {
      device_id: "web_normal",
      metrics: { temperature: 30.0, humidity: 50.0, gas: 0.1, vibration: 0.5, current: 1.0 },
      system_state: { cloud_connected: true, voice_state: "idle", sensor_online: true },
    },
    temperature_warning: {
      device_id: "web_temperature_warning",
      metrics: { temperature: 65.0, humidity: 50.0, gas: 0.1, vibration: 0.5, current: 1.0 },
      system_state: { cloud_connected: true, voice_state: "idle", sensor_online: true },
    },
    gas_alarm: {
      device_id: "web_gas_alarm",
      metrics: { temperature: 30.0, humidity: 50.0, gas: 0.65, vibration: 0.5, current: 1.0 },
      system_state: { cloud_connected: true, voice_state: "idle", sensor_online: true },
    },
    vibration_alarm: {
      device_id: "web_vibration_alarm",
      metrics: { temperature: 30.0, humidity: 50.0, gas: 0.1, vibration: 2.8, current: 1.0 },
      system_state: { cloud_connected: true, voice_state: "idle", sensor_online: true },
    },
    sensor_offline: {
      device_id: "web_sensor_offline",
      metrics: { temperature: 30.0, humidity: 50.0, gas: 0.1, vibration: 0.5, current: 1.0 },
      system_state: { cloud_connected: true, voice_state: "idle", sensor_online: false },
    },
  },
};

const els = {
  pageTabs: Array.from(document.querySelectorAll("[data-page-tab]")),
  pageViews: Array.from(document.querySelectorAll("[data-page-view]")),
  apiBaseInput: document.querySelector("#apiBaseInput"),
  refreshButton: document.querySelector("#refreshButton"),
  connectionBadge: document.querySelector("#connectionBadge"),
  deviceTotal: document.querySelector("#deviceTotal"),
  onlineTotal: document.querySelector("#onlineTotal"),
  onlineRatio: document.querySelector("#onlineRatio"),
  activeAlarmTotal: document.querySelector("#activeAlarmTotal"),
  metricTotal: document.querySelector("#metricTotal"),
  metricNames: document.querySelector("#metricNames"),
  lastUpdated: document.querySelector("#lastUpdated"),
  metricBoard: document.querySelector("#metricBoard"),
  alarmList: document.querySelector("#alarmList"),
  deviceList: document.querySelector("#deviceList"),
  deviceStatusText: document.querySelector("#deviceStatusText"),
  commandDevice: document.querySelector("#commandDevice"),
  commandType: document.querySelector("#commandType"),
  commandPayload: document.querySelector("#commandPayload"),
  commandForm: document.querySelector("#commandForm"),
  commandResult: document.querySelector("#commandResult"),
  loadAlarmsButton: document.querySelector("#loadAlarmsButton"),
  metricChart: document.querySelector("#metricChart"),
  evaluateScenario: document.querySelector("#evaluateScenario"),
  evaluateModel: document.querySelector("#evaluateModel"),
  evaluateDebug: document.querySelector("#evaluateDebug"),
  evaluateRealLlm: document.querySelector("#evaluateRealLlm"),
  runEvaluateButton: document.querySelector("#runEvaluateButton"),
  evaluateStatus: document.querySelector("#evaluateStatus"),
  evaluateResult: document.querySelector("#evaluateResult"),
};

els.apiBaseInput.value = state.apiBase;

function getInitialPage() {
  const page = window.location.hash.replace("#", "").trim();
  return PAGE_NAMES.includes(page) ? page : "overview";
}

function setActivePage(page, updateHash = true) {
  const nextPage = PAGE_NAMES.includes(page) ? page : "overview";
  state.activePage = nextPage;

  els.pageTabs.forEach((tab) => {
    const selected = tab.dataset.pageTab === nextPage;
    tab.classList.toggle("is-active", selected);
    tab.setAttribute("aria-selected", selected ? "true" : "false");
  });

  els.pageViews.forEach((view) => {
    view.classList.toggle("is-active", view.dataset.pageView === nextPage);
  });

  if (updateHash && window.location.hash !== `#${nextPage}`) {
    window.history.replaceState(null, "", `#${nextPage}`);
  }

  if (nextPage === "monitor") {
    redrawChartSoon();
  }
}

function redrawChartSoon() {
  window.requestAnimationFrame(() => {
    drawChart(latestMetrics().slice(0, 10));
  });
}

function defaultApiBase() {
  if (window.location.protocol === "http:" || window.location.protocol === "https:") {
    return window.location.origin;
  }
  return localStorage.getItem("safecloud.apiBase") || "http://127.0.0.1:8000";
}

function apiUrl(path) {
  return `${state.apiBase.replace(/\/$/, "")}${path}`;
}

async function request(path, options = {}) {
  const response = await fetch(apiUrl(path), {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${response.status} ${detail}`);
  }
  return response.json();
}

function setConnection(ok, text) {
  els.connectionBadge.textContent = text;
  els.connectionBadge.classList.toggle("is-muted", !ok);
  els.connectionBadge.classList.toggle("is-error", !ok && text !== "未连接" && text !== "连接中");
}

function formatTime(value) {
  if (!value) return "未记录";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

function formatValue(value) {
  if (typeof value === "number") return Number.isInteger(value) ? `${value}` : value.toFixed(1);
  if (typeof value === "boolean") return value ? "true" : "false";
  return `${value}`;
}

function cleanText(value, fallback) {
  const text = value ? `${value}`.trim() : "";
  if (!text || /^[?\s]+$/.test(text)) return fallback;
  return text;
}

function escapeHtml(value) {
  return `${value ?? ""}`
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function alarmLevelClass(level) {
  if (Number(level) >= 2) return "critical";
  if (Number(level) === 1) return "warning";
  return "normal";
}

function alarmLabel(level) {
  if (Number(level) >= 2 || level === "critical") return "高危";
  if (Number(level) === 1 || level === "warning") return "预警";
  if (level === "active") return "激活";
  return "正常";
}

function metricLabel(name) {
  const labels = {
    temperature: "温度",
    humidity: "湿度",
    gas: "气体",
    smoke: "烟雾",
    light: "光照",
    noise: "噪声",
    voltage: "电压",
    current: "电流",
    vibration: "振动",
    tvoc: "TVOC",
    eco2: "eCO2",
    mq3_value: "MQ-3",
    flame_detected: "火焰",
    risk_score: "风险分",
  };
  return labels[name] || name;
}

function normalizeMetric(name, value) {
  const numeric = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numeric)) return 0;
  const scale = {
    temperature: 80,
    humidity: 100,
    gas: 1,
    smoke: 300,
    light: 1000,
    noise: 120,
    voltage: 300,
    current: 30,
    vibration: 3,
    tvoc: 1000,
    eco2: 5000,
    mq3_value: 1,
    risk_score: 100,
  }[name] || Math.max(100, numeric);
  return Math.max(0, Math.min(1, numeric / scale));
}

function latestMetrics() {
  const rows = state.summary?.latest_telemetry || [];
  return rows.flatMap((item) =>
    Object.entries(item.metrics || {}).map(([name, value]) => ({
      deviceId: item.device_id,
      timestamp: item.timestamp,
      name,
      value,
    })),
  );
}

function renderKpis() {
  const summary = state.summary || {};
  const total = summary.device_total || 0;
  const online = summary.online_device_total || 0;
  const metrics = summary.metric_names || [];
  els.deviceTotal.textContent = total;
  els.onlineTotal.textContent = online;
  els.activeAlarmTotal.textContent = summary.active_alarm_total || 0;
  els.metricTotal.textContent = metrics.length;
  els.onlineRatio.textContent = total ? `${Math.round((online / total) * 100)}% 在线率` : "0% 在线率";
  els.metricNames.textContent = metrics.length ? metrics.slice(0, 4).map(metricLabel).join(" / ") : "暂无指标";
  els.lastUpdated.textContent = `刷新于 ${new Date().toLocaleTimeString("zh-CN", { hour12: false })}`;
}

function renderMetrics() {
  const metrics = latestMetrics();
  if (!metrics.length) {
    els.metricBoard.className = "metric-board empty-state";
    els.metricBoard.textContent = "暂无遥测数据";
    drawChart([]);
    return;
  }

  els.metricBoard.className = "metric-board";
  els.metricBoard.innerHTML = metrics
    .slice(0, 12)
    .map(
      (metric) => `
        <div class="metric-card">
          <span class="metric-name">${escapeHtml(metricLabel(metric.name))}</span>
          <span class="metric-value">${escapeHtml(formatValue(metric.value))}</span>
          <span class="metric-device">${escapeHtml(metric.deviceId)} · ${escapeHtml(formatTime(metric.timestamp))}</span>
        </div>
      `,
    )
    .join("");
  drawChart(metrics.slice(0, 10));
}

function renderAlarms(source = state.summary?.recent_alarms || []) {
  if (!source.length) {
    els.alarmList.className = "list empty-state";
    els.alarmList.textContent = "暂无报警";
    return;
  }

  els.alarmList.className = "list";
  els.alarmList.innerHTML = source
    .slice(0, 12)
    .map((alarm) => {
      const levelClass = alarmLevelClass(alarm.alarm_level);
      return `
        <div class="alarm-item">
          <div class="alarm-top">
            <span class="alarm-title">${escapeHtml(metricLabel(alarm.metric_name || alarm.alarm_type || "alarm"))}</span>
            <span class="pill ${levelClass}">${escapeHtml(alarmLabel(alarm.alarm_level))}</span>
          </div>
          <span>${escapeHtml(alarm.alarm_message || "无报警详情")}</span>
          <span class="muted">${escapeHtml(alarm.device_id || "-")} · ${escapeHtml(formatTime(alarm.created_at))}</span>
        </div>
      `;
    })
    .join("");
}

function renderDevices() {
  const devices = state.devices || [];
  const counts = state.summary?.device_status || {};
  els.deviceStatusText.textContent =
    Object.entries(counts)
      .map(([key, value]) => `${key}: ${value}`)
      .join(" / ") || "暂无设备";

  if (!devices.length) {
    els.deviceList.className = "device-list empty-state";
    els.deviceList.textContent = "暂无设备";
    els.commandDevice.innerHTML = "";
    return;
  }

  els.deviceList.className = "device-list";
  els.deviceList.innerHTML = devices
    .map((device) => {
      const name = cleanText(device.device_name, device.device_id);
      const location = cleanText(device.location, "未设置位置");
      const statusClass = device.status === "online" ? "normal" : device.status === "offline" ? "warning" : "active";
      return `
        <div class="device-item">
          <div class="device-top">
            <span class="device-title">${escapeHtml(name)}</span>
            <span class="pill ${statusClass}">${escapeHtml(device.status || "unknown")}</span>
          </div>
          <span class="muted">${escapeHtml(device.device_id)} · ${escapeHtml(device.device_type || "-")}</span>
          <span>${escapeHtml(location)}</span>
          <span class="muted">last seen: ${escapeHtml(formatTime(device.last_seen))}</span>
        </div>
      `;
    })
    .join("");

  const current = els.commandDevice.value;
  els.commandDevice.innerHTML = devices
    .map((device) => `<option value="${escapeHtml(device.device_id)}">${escapeHtml(device.device_id)}</option>`)
    .join("");
  if (current) els.commandDevice.value = current;
}

function resizeCanvas(canvas) {
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  const cssWidth = rect.width || canvas.parentElement?.clientWidth || 720;
  const nextWidth = Math.max(320, Math.round(cssWidth * ratio));
  const nextHeight = Math.round(260 * ratio);
  if (canvas.width !== nextWidth || canvas.height !== nextHeight) {
    canvas.width = nextWidth;
    canvas.height = nextHeight;
  }
  return { width: nextWidth, height: nextHeight, ratio };
}

function drawChart(metrics) {
  const canvas = els.metricChart;
  const ctx = canvas.getContext("2d");
  const { width, height, ratio } = resizeCanvas(canvas);
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#f8faf6";
  ctx.fillRect(0, 0, width, height);

  const font = (size, weight = "400") => `${weight} ${Math.round(size * ratio)}px Segoe UI, Microsoft YaHei, Arial`;
  const padding = 34 * ratio;

  if (!metrics.length) {
    ctx.fillStyle = "#64726b";
    ctx.font = font(15, "700");
    ctx.fillText("暂无指标快照", padding, 52 * ratio);
    return;
  }

  const chartWidth = width - padding * 2;
  const barGap = 12 * ratio;
  const barWidth = Math.max(22 * ratio, (chartWidth - barGap * (metrics.length - 1)) / metrics.length);
  const baseline = height - 46 * ratio;
  const maxHeight = height - 88 * ratio;
  const palette = ["#1f7885", "#1f6f58", "#b3822c", "#496f97", "#b7463f"];

  ctx.strokeStyle = "#d9e2dc";
  ctx.lineWidth = ratio;
  for (let i = 0; i < 4; i += 1) {
    const y = 28 * ratio + i * (maxHeight / 3);
    ctx.beginPath();
    ctx.moveTo(padding, y);
    ctx.lineTo(width - padding, y);
    ctx.stroke();
  }

  metrics.forEach((metric, index) => {
    const x = padding + index * (barWidth + barGap);
    const normalized = normalizeMetric(metric.name, metric.value);
    const barHeight = Math.max(4 * ratio, normalized * maxHeight);
    const y = baseline - barHeight;
    ctx.fillStyle = palette[index % palette.length];
    ctx.fillRect(x, y, barWidth, barHeight);

    ctx.fillStyle = "#17211d";
    ctx.font = font(13, "800");
    ctx.fillText(formatValue(metric.value), x, y - 8 * ratio);

    ctx.fillStyle = "#64726b";
    ctx.font = font(12, "700");
    const label = metricLabel(metric.name);
    const clippedLabel = label.length > 8 ? `${label.slice(0, 7)}…` : label;
    ctx.fillText(clippedLabel, x, baseline + 22 * ratio);
  });
}

async function refresh() {
  state.apiBase = els.apiBaseInput.value.trim() || "http://127.0.0.1:8000";
  localStorage.setItem("safecloud.apiBase", state.apiBase);
  setConnection(false, "连接中");
  try {
    const [summary, devices] = await Promise.all([
      request("/api/dashboard/summary"),
      request("/api/devices"),
    ]);
    state.summary = summary;
    state.devices = devices;
    renderKpis();
    renderMetrics();
    renderAlarms();
    renderDevices();
    setConnection(true, "已连接");
  } catch (error) {
    console.error(error);
    setConnection(false, "连接失败");
  }
}

async function loadAllAlarms() {
  try {
    const alarms = await request("/api/alarms");
    state.alarms = alarms;
    renderAlarms(alarms);
  } catch (error) {
    console.error(error);
    els.alarmList.className = "list empty-state";
    els.alarmList.textContent = "报警加载失败";
  }
}

async function submitCommand(event) {
  event.preventDefault();
  const deviceId = els.commandDevice.value;
  if (!deviceId) {
    els.commandResult.textContent = "没有可用设备";
    return;
  }

  let payload;
  try {
    payload = JSON.parse(els.commandPayload.value);
  } catch {
    els.commandResult.textContent = "参数 JSON 无效";
    return;
  }

  try {
    const command = await request("/api/commands", {
      method: "POST",
      body: JSON.stringify({
        device_id: deviceId,
        command_type: els.commandType.value,
        command_payload: payload,
      }),
    });
    els.commandResult.textContent = `已创建 ${command.command_id}`;
  } catch (error) {
    console.error(error);
    els.commandResult.textContent = "命令下发失败";
  }
}

async function runEvaluate() {
  const scenarioName = els.evaluateScenario.value;
  const scenario = state.evaluateScenarios[scenarioName] || state.evaluateScenarios.normal;
  const payload = JSON.parse(JSON.stringify(scenario));
  payload.include_debug = els.evaluateDebug.checked;
  payload.use_real_llm = els.evaluateRealLlm.checked;
  payload.force_model = els.evaluateModel.value;

  els.runEvaluateButton.disabled = true;
  els.evaluateStatus.textContent = "评估中";
  els.evaluateResult.className = "evaluate-result empty-state";
  els.evaluateResult.textContent = "正在调用 /api/evaluate";

  try {
    const result = await request("/api/evaluate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    renderEvaluateResult(result);
    els.evaluateStatus.textContent = "已完成";
  } catch (error) {
    console.error(error);
    els.evaluateStatus.textContent = "评估失败";
    els.evaluateResult.className = "evaluate-result empty-state";
    els.evaluateResult.textContent = `调用失败：${error.message}`;
  } finally {
    els.runEvaluateButton.disabled = false;
  }
}

function renderEvaluateResult(result) {
  const status = result.final_status || {};
  const debug = result.debug || {};
  const models = debug.model_results || [];
  const router = debug.router || {};
  const level = Number(status.alarm_level ?? 0);

  const modelHtml = models.length
    ? models
        .map(
          (model) => `
            <div class="model-result-card">
              <div class="model-card-top">
                <strong>${escapeHtml(model.model_name || "model")}</strong>
                <span class="pill ${alarmLevelClass(model.alarm_level)}">L${escapeHtml(model.alarm_level ?? "-")}</span>
              </div>
              <span class="muted">confidence: ${escapeHtml(model.confidence ?? "-")}</span>
              <p>${escapeHtml(model.risk_summary || model.error || "无摘要")}</p>
            </div>
          `,
        )
        .join("")
    : `<div class="model-result-card"><p>未返回模型明细</p></div>`;

  els.evaluateResult.className = "evaluate-result";
  els.evaluateResult.innerHTML = `
    <div class="final-status">
      <span class="pill ${alarmLevelClass(level)}">L${escapeHtml(level)}</span>
      <strong>${escapeHtml(status.status_text || "未知")}</strong>
      <span class="muted">${escapeHtml(status.analysis_mode || "unknown")}</span>
    </div>
    <div class="status-line">
      <span>设备</span>
      <strong>${escapeHtml(status.device_id || "-")}</strong>
    </div>
    <div class="status-line">
      <span>原因</span>
      <p>${escapeHtml(status.reason || "-")}</p>
    </div>
    <div class="status-line">
      <span>建议</span>
      <p>${escapeHtml(status.suggestion || "-")}</p>
    </div>
    <div class="status-line">
      <span>播报</span>
      <p>${escapeHtml(status.voice_text || "-")}</p>
    </div>
    <div class="status-line">
      <span>路由</span>
      <p>${escapeHtml((router.selected_models || []).join(" / ") || "无")}</p>
    </div>
    <div class="model-result-grid">${modelHtml}</div>
  `;
}

els.pageTabs.forEach((tab) => {
  tab.addEventListener("click", () => setActivePage(tab.dataset.pageTab));
});
els.refreshButton.addEventListener("click", refresh);
els.apiBaseInput.addEventListener("change", refresh);
els.loadAlarmsButton.addEventListener("click", loadAllAlarms);
els.commandForm.addEventListener("submit", submitCommand);
els.runEvaluateButton.addEventListener("click", runEvaluate);
window.addEventListener("hashchange", () => setActivePage(getInitialPage(), false));
window.addEventListener("resize", () => {
  if (state.activePage === "monitor") redrawChartSoon();
});

setActivePage(state.activePage, false);
refresh();
setInterval(refresh, 8000);
