const PAGE_NAMES = ["overview", "monitor", "analysis", "vision", "operations"];

const state = {
  apiBase: defaultApiBase(),
  activePage: getInitialPage(),
  summary: null,
  latestEvaluation: null,
  latestVision: null,
  devices: [],
  alarms: [],
  evaluateScenarios: {
    normal: {
      device_id: "board_2k0301",
      metrics: {
        temperature: 25.0,
        humidity: 55.0,
        tvoc: 120,
        eco2: 450,
        mq3_value: 0.123,
        flame_detected: false,
        risk_score: 0,
      },
      system_state: { cloud_connected: true, voice_state: "idle", sensor_online: true, actuator_online: true, source: "2k0301" },
    },
    temperature_warning: {
      device_id: "board_2k0301",
      metrics: {
        temperature: 65.0,
        humidity: 52.0,
        tvoc: 180,
        eco2: 620,
        mq3_value: 0.08,
        flame_detected: false,
        risk_score: 35,
      },
      system_state: { cloud_connected: true, voice_state: "idle", sensor_online: true, actuator_online: true, source: "2k0301" },
    },
    gas_alarm: {
      device_id: "board_2k0301",
      metrics: {
        temperature: 31.0,
        humidity: 58.0,
        tvoc: 2600,
        eco2: 2400,
        mq3_value: 0.86,
        flame_detected: false,
        risk_score: 78,
      },
      system_state: { cloud_connected: true, voice_state: "idle", sensor_online: true, actuator_online: true, source: "2k0301" },
    },
    flame_alarm: {
      device_id: "board_2k0301",
      metrics: {
        temperature: 43.0,
        humidity: 41.0,
        tvoc: 900,
        eco2: 1200,
        mq3_value: 0.18,
        flame_detected: true,
        risk_score: 92,
      },
      system_state: { cloud_connected: true, voice_state: "idle", sensor_online: true, actuator_online: true, source: "2k0301" },
    },
    sensor_offline: {
      device_id: "board_2k0301",
      metrics: {
        temperature: 0.0,
        humidity: 0.0,
        tvoc: 0,
        eco2: 0,
        mq3_value: 0,
        flame_detected: false,
        risk_score: 0,
      },
      system_state: { cloud_connected: true, voice_state: "idle", sensor_online: false, actuator_online: false, source: "2k0301" },
    },
  },
};

const SENSOR_METRIC_ORDER = ["temperature", "humidity", "tvoc", "eco2", "mq3_value", "flame_detected", "risk_score"];

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
  commandAck: document.querySelector("#commandAck"),
  loadAlarmsButton: document.querySelector("#loadAlarmsButton"),
  metricChart: document.querySelector("#metricChart"),
  evaluateScenario: document.querySelector("#evaluateScenario"),
  evaluateModel: document.querySelector("#evaluateModel"),
  evaluateDebug: document.querySelector("#evaluateDebug"),
  evaluateRealLlm: document.querySelector("#evaluateRealLlm"),
  runEvaluateButton: document.querySelector("#runEvaluateButton"),
  evaluateStatus: document.querySelector("#evaluateStatus"),
  evaluateResult: document.querySelector("#evaluateResult"),
  visionModeText: document.querySelector("#visionModeText"),
  visionImage: document.querySelector("#visionImage"),
  visionImageEmpty: document.querySelector("#visionImageEmpty"),
  visionStatusPill: document.querySelector("#visionStatusPill"),
  visionPerson: document.querySelector("#visionPerson"),
  visionHelmet: document.querySelector("#visionHelmet"),
  visionMask: document.querySelector("#visionMask"),
  visionVest: document.querySelector("#visionVest"),
  visionSummary: document.querySelector("#visionSummary"),
  visionMissing: document.querySelector("#visionMissing"),
  visionBackend: document.querySelector("#visionBackend"),
  visionModeButtons: Array.from(document.querySelectorAll("[data-vision-mode]")),
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

async function requestOptional(path) {
  try {
    return await request(path);
  } catch (error) {
    if (`${error.message || ""}`.startsWith("404 ")) return null;
    console.warn(`optional request failed: ${path}`, error);
    return null;
  }
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

function numberText(value, digits = 1) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return `${value ?? "--"}`;
  if (Number.isInteger(numeric)) return `${numeric}`;
  return numeric.toFixed(digits).replace(/\.?0+$/, "");
}

function formatMetricValue(name, value, options = {}) {
  const short = options.short === true;
  if (name === "flame_detected") {
    const detected = value === true || value === "true" || value === 1 || value === "1";
    return detected ? (short ? "有火焰" : "检测到火焰") : (short ? "无火焰" : "未检测到火焰");
  }
  if (typeof value === "boolean") return value ? "是" : "否";
  const numeric = Number(value);
  if (name === "temperature" && Number.isFinite(numeric) && numeric <= -900) return "暂无数据";
  if (name === "humidity" && Number.isFinite(numeric) && numeric < 0) return "暂无数据";

  const units = {
    temperature: "℃",
    humidity: "%RH",
    tvoc: "ppb",
    eco2: "ppm",
    mq3_value: "mg/L",
    gas: "",
    risk_score: "/100",
  };
  const digits = {
    temperature: 1,
    humidity: 1,
    tvoc: 0,
    eco2: 0,
    mq3_value: 3,
    gas: 3,
    risk_score: 0,
  }[name] ?? 1;
  const text = numberText(value, digits);
  const unit = units[name];
  if (!unit) return text;
  return name === "risk_score" ? `${text} ${unit}` : `${text} ${unit}`;
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

function ppeStatusLabel(status) {
  const labels = {
    pass: "防护合规",
    fail: "防护缺失",
    unknown: "等待识别",
    processing: "检测中",
    error: "视觉异常",
  };
  return labels[status] || "等待识别";
}

function ppeStatusClass(status) {
  if (status === "fail" || status === "error") return "critical";
  if (status === "unknown" || status === "processing") return "warning";
  return "normal";
}

function boolLabel(value, trueText = "是", falseText = "否", unknownText = "未确认") {
  if (value === true) return trueText;
  if (value === false) return falseText;
  return unknownText;
}

function deviceStatusLabel(status) {
  const labels = {
    online: "在线",
    offline: "离线",
    maintenance: "维护中",
    unknown: "未知",
  };
  return labels[status] || status || "未知";
}

function metricLabel(name) {
  const labels = {
    temperature: "温度",
    humidity: "湿度",
    gas: "归一化气体风险",
    smoke: "烟雾",
    light: "光照",
    noise: "噪声",
    voltage: "电压",
    current: "电流",
    vibration: "振动",
    tvoc: "TVOC",
    eco2: "eCO2",
    mq3_value: "MQ-3 乙醇",
    flame_detected: "火焰检测",
    risk_score: "综合风险",
    sensor_online: "采集板在线",
  };
  return labels[name] || name;
}

function normalizeMetric(name, value) {
  if (name === "flame_detected") {
    return value === true || value === "true" || value === 1 || value === "1" ? 1 : 0;
  }
  const numeric = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numeric)) return 0;
  if (name === "temperature" && numeric <= -900) return 0;
  if (name === "humidity" && numeric < 0) return 0;
  if (name === "eco2") return Math.max(0, Math.min(1, (numeric - 400) / 1600));
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
    tvoc: 2000,
    mq3_value: 1,
    risk_score: 100,
  }[name] || Math.max(100, numeric);
  return Math.max(0, Math.min(1, numeric / scale));
}

function latestMetrics() {
  const evaluateMetrics = latestEvaluateMetrics();
  if (evaluateMetrics.length) return evaluateMetrics;

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

function hasOwn(object, key) {
  return Object.prototype.hasOwnProperty.call(object || {}, key);
}

function sensorMetricsFromStatus(status) {
  const nested = status?.sensor_metrics || {};
  const metrics = {};
  SENSOR_METRIC_ORDER.forEach((name) => {
    if (hasOwn(nested, name)) {
      metrics[name] = nested[name];
    } else if (hasOwn(status, name)) {
      metrics[name] = status[name];
    }
  });
  return metrics;
}

function latestEvaluateMetrics() {
  const latest = state.latestEvaluation;
  const status = latest?.response?.final_status;
  if (!status) return [];
  const metrics = sensorMetricsFromStatus(status);
  return SENSOR_METRIC_ORDER.filter((name) => hasOwn(metrics, name)).map((name) => ({
    deviceId: status.device_id || latest.request?.device_id || "board_2k0301",
    timestamp: status.timestamp || latest.request?.timestamp,
    name,
    value: metrics[name],
  }));
}

function latestEvaluateStatus() {
  return state.latestEvaluation?.response?.final_status || null;
}

function liveDeviceSummary() {
  const status = latestEvaluateStatus();
  if (!status) return null;
  const gatewayOnline = status.cloud_connected !== false;
  const sensorOnline = status.sensor_online !== false;
  return {
    total: 2,
    online: Number(gatewayOnline) + Number(sensorOnline),
    counts: {
      online: Number(gatewayOnline) + Number(sensorOnline),
      offline: 2 - (Number(gatewayOnline) + Number(sensorOnline)),
    },
    devices: [
      {
        device_id: "board_2k1000la",
        device_name: "龙芯 2K1000LA 主控",
        device_type: "HMI / 语音 / 视觉 / 云端桥接",
        status: gatewayOnline ? "online" : "offline",
        location: "主控节点",
        last_seen: status.timestamp,
      },
      {
        device_id: status.device_id || "board_2k0301",
        device_name: "龙芯 2K0301 采集与执行板",
        device_type: "传感器采集 / 执行控制",
        status: sensorOnline ? "online" : "offline",
        location: status.sensor_source || "MQTT 板间通信",
        last_seen: status.timestamp,
      },
    ],
  };
}

function liveAlarmItems() {
  const status = latestEvaluateStatus();
  if (!status) return null;
  const level = Number(status.alarm_level || 0);
  if (level <= 0) return [];
  return [
    {
      alarm_id: `eval-${status.timestamp || Date.now()}`,
      device_id: status.device_id || "board_2k0301",
      alarm_type: "safety_evaluate",
      alarm_level: level,
      alarm_message: status.reason || status.status_text || "当前存在风险报警",
      metric_name: status.sensor_online === false ? "sensor_online" : "risk_score",
      metric_value: status.sensor_online === false ? 0 : status.risk_score,
      threshold_value: level,
      status: "active",
      created_at: status.timestamp,
    },
  ];
}

function renderKpis() {
  const summary = state.summary || {};
  const liveDevices = liveDeviceSummary();
  const liveAlarms = liveAlarmItems();
  const total = liveDevices ? liveDevices.total : summary.device_total || 0;
  const online = liveDevices ? liveDevices.online : summary.online_device_total || 0;
  const evaluateMetrics = latestEvaluateMetrics().map((metric) => metric.name);
  const metrics = evaluateMetrics.length ? evaluateMetrics : summary.metric_names || [];
  els.deviceTotal.textContent = total;
  els.onlineTotal.textContent = online;
  els.activeAlarmTotal.textContent = liveAlarms ? liveAlarms.length : summary.active_alarm_total || 0;
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
          <span class="metric-value">${escapeHtml(formatMetricValue(metric.name, metric.value))}</span>
          <span class="metric-device">${escapeHtml(metric.deviceId)} · ${escapeHtml(formatTime(metric.timestamp))}</span>
        </div>
      `,
    )
    .join("");
  drawChart(metrics.slice(0, 10));
}

function renderAlarms(source = null) {
  if (source === null) {
    const liveAlarms = liveAlarmItems();
    source = liveAlarms !== null ? liveAlarms : state.summary?.recent_alarms || [];
  }
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
  const liveDevices = liveDeviceSummary();
  const devices = liveDevices ? liveDevices.devices : state.devices || [];
  const counts = liveDevices ? liveDevices.counts : state.summary?.device_status || {};
  els.deviceStatusText.textContent =
    Object.entries(counts)
      .map(([key, value]) => `${deviceStatusLabel(key)}: ${value}`)
      .join(" / ") || "暂无设备";

  if (!devices.length) {
    els.deviceList.className = "device-list empty-state";
    els.deviceList.textContent = "暂无设备";
    renderCommandTargets(devices);
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
            <span class="pill ${statusClass}">${escapeHtml(deviceStatusLabel(device.status))}</span>
          </div>
          <span class="muted">${escapeHtml(device.device_id)} · ${escapeHtml(device.device_type || "-")}</span>
          <span>${escapeHtml(location)}</span>
          <span class="muted">最后在线：${escapeHtml(formatTime(device.last_seen))}</span>
        </div>
      `;
    })
    .join("");

  renderCommandTargets(devices);
}

function renderCommandTargets(devices) {
  const current = els.commandDevice.value;
  const commandTargets = [...(devices || [])];
  if (!commandTargets.some((device) => device.device_id === "board_2k0301")) {
    commandTargets.unshift({ device_id: "board_2k0301" });
  }
  els.commandDevice.innerHTML = commandTargets
    .map((device) => `<option value="${escapeHtml(device.device_id)}">${escapeHtml(device.device_id)}</option>`)
    .join("");
  if (current && commandTargets.some((device) => device.device_id === current)) {
    els.commandDevice.value = current;
  }
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
    ctx.fillText(formatMetricValue(metric.name, metric.value, { short: true }), x, y - 8 * ratio);

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
    const [summary, devices, latestEvaluation, latestVision] = await Promise.all([
      request("/api/dashboard/summary"),
      request("/api/devices"),
      requestOptional("/api/evaluate/latest"),
      requestOptional("/api/vision/latest"),
    ]);
    state.summary = summary;
    state.devices = devices;
    state.latestEvaluation = latestEvaluation;
    state.latestVision = latestVision;
    renderKpis();
    renderMetrics();
    renderAlarms();
    renderDevices();
    renderVision();
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

async function submitCommandV2(event) {
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

  const submitButton = els.commandForm.querySelector("button[type='submit']");
  try {
    submitButton.disabled = true;
    els.commandResult.textContent = "正在下发并等待 ACK";
    els.commandAck.className = "command-ack empty-state";
    els.commandAck.textContent = "waiting...";
    const command = await request("/api/commands", {
      method: "POST",
      body: JSON.stringify({
        device_id: deviceId,
        command_type: els.commandType.value,
        command_payload: payload,
      }),
    });
    renderCommandResult(command);
  } catch (error) {
    console.error(error);
    els.commandResult.textContent = "命令下发失败";
    els.commandAck.className = "command-ack empty-state";
    els.commandAck.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
}

function renderCommandResult(command) {
  const ack = command.ack || null;
  if (command.delivery_status) {
    const ok = command.status === "executed" || ack?.ok === true;
    const message = ack?.message || command.result_message || command.delivery_status;
    els.commandResult.textContent = `${ok ? "ACK 成功" : "ACK 失败"} · ${message}`;
    els.commandAck.className = `command-ack ${ok ? "is-ok" : "is-error"}`;
    els.commandAck.textContent = JSON.stringify(
      {
        command_id: command.command_id,
        status: command.status,
        delivery_status: command.delivery_status,
        elapsed_ms: command.delivery_elapsed_ms,
        ack,
        transport_error: command.transport_error,
      },
      null,
      2,
    );
    return;
  }

  els.commandResult.textContent = `已创建 ${command.command_id}`;
  els.commandAck.className = "command-ack empty-state";
  els.commandAck.textContent = "当前 SafeCloud 未启用 MQTT 直连，命令已进入待执行队列。";
}

function commandPreset(commandType) {
  const presets = {
    fan_control: { state: "on", speed: 60, duration_ms: 1000 },
    buzzer_control: { state: "on", pattern: "fast", duration_ms: 1000 },
    alarm_light: { color: "red", mode: "blink", duration_ms: 1000 },
    device_reset: { target: "actuator_state" },
  };
  return presets[commandType] || {};
}

function refreshCommandPreset() {
  els.commandPayload.value = JSON.stringify(commandPreset(els.commandType.value), null, 2);
}

async function runEvaluate() {
  const scenarioName = els.evaluateScenario.value;
  const scenario = state.evaluateScenarios[scenarioName] || state.evaluateScenarios.normal;
  const payload = JSON.parse(JSON.stringify(scenario));
  payload.include_debug = els.evaluateDebug.checked;
  payload.use_real_llm = els.evaluateRealLlm.checked;
  payload.force_model = els.evaluateModel.value;

  if (payload.use_real_llm && payload.force_model === "mock") {
    els.evaluateStatus.textContent = "配置冲突";
    els.evaluateResult.className = "evaluate-result empty-state";
    els.evaluateResult.textContent = "真实 LLM 模式不能强制选择 mock，请选择自动仲裁或真实模型。";
    return;
  }

  els.runEvaluateButton.disabled = true;
  els.evaluateStatus.textContent = "评估中";
  els.evaluateResult.className = "evaluate-result empty-state";
  els.evaluateResult.textContent = "正在调用 /api/evaluate";

  try {
    const result = await request("/api/evaluate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.latestEvaluation = { request: payload, response: result };
    renderEvaluateResult(result);
    renderKpis();
    renderMetrics();
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

function renderSensorMetricGrid(status) {
  const metrics = sensorMetricsFromStatus(status);
  const cards = SENSOR_METRIC_ORDER.filter((name) => hasOwn(metrics, name)).map(
    (name) => `
      <div class="sensor-result-card">
        <span>${escapeHtml(metricLabel(name))}</span>
        <strong>${escapeHtml(formatMetricValue(name, metrics[name]))}</strong>
      </div>
    `,
  );
  if (!cards.length) {
    return `<div class="sensor-result-card"><span>301 传感器</span><strong>暂无数据</strong></div>`;
  }
  return cards.join("");
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
    <div class="sensor-result-grid">${renderSensorMetricGrid(status)}</div>
    <div class="status-line">
      <span>路由</span>
      <p>${escapeHtml((router.selected_models || []).join(" / ") || "无")}</p>
    </div>
    <div class="model-result-grid">${modelHtml}</div>
  `;
}

function renderVision() {
  const status = state.latestVision?.response?.vision_status || state.latestVision?.vision_status || null;
  if (!status) {
    els.visionModeText.textContent = "等待视觉服务";
    els.visionStatusPill.className = "pill warning";
    els.visionStatusPill.textContent = "等待识别";
    els.visionPerson.textContent = "--";
    els.visionHelmet.textContent = "--";
    els.visionMask.textContent = "--";
    els.visionVest.textContent = "--";
    els.visionSummary.textContent = "等待 2K1000LA 摄像头服务写入结果";
    els.visionMissing.textContent = "--";
    els.visionBackend.textContent = "--";
    els.visionImage.removeAttribute("src");
    els.visionImage.classList.remove("is-visible");
    els.visionImageEmpty.classList.remove("is-hidden");
    return;
  }

  const ppe = status.ppe_status || "unknown";
  els.visionModeText.textContent = `模式 ${status.mode || "--"} / 延迟 ${status.latency_ms ?? "--"} ms`;
  els.visionStatusPill.className = `pill ${ppeStatusClass(ppe)}`;
  els.visionStatusPill.textContent = ppeStatusLabel(ppe);
  els.visionPerson.textContent = boolLabel(status.person_detected, "检测到", "未检测到");
  els.visionHelmet.textContent = boolLabel(status.helmet_detected, "已佩戴", "未佩戴");
  els.visionMask.textContent = boolLabel(status.mask_detected, "已佩戴", "未佩戴");
  els.visionVest.textContent = boolLabel(status.reflective_vest_detected, "已穿戴", "未穿戴");
  els.visionSummary.textContent = status.error || status.summary || "等待视觉结果";
  els.visionMissing.textContent = (status.missing_ppe || []).length ? status.missing_ppe.join(" / ") : "无";
  els.visionBackend.textContent = `${status.backend || "--"} / 摄像头${status.camera_online ? "在线" : "离线"}`;

  if (status.image_available) {
    els.visionImage.src = apiUrl(`/api/vision/latest-image?t=${Date.now()}`);
    els.visionImage.classList.add("is-visible");
    els.visionImageEmpty.classList.add("is-hidden");
  } else {
    els.visionImage.removeAttribute("src");
    els.visionImage.classList.remove("is-visible");
    els.visionImageEmpty.classList.remove("is-hidden");
  }
}

async function setVisionMode(mode) {
  try {
    const result = await request("/api/vision/mode", {
      method: "POST",
      body: JSON.stringify({ mode }),
    });
    els.visionModeText.textContent = `模式切换请求：${result.mode}`;
  } catch (error) {
    console.error(error);
    els.visionModeText.textContent = `模式切换失败：${error.message}`;
  }
}

els.pageTabs.forEach((tab) => {
  tab.addEventListener("click", () => setActivePage(tab.dataset.pageTab));
});
els.refreshButton.addEventListener("click", refresh);
els.apiBaseInput.addEventListener("change", refresh);
els.loadAlarmsButton.addEventListener("click", loadAllAlarms);
els.commandForm.addEventListener("submit", submitCommandV2);
els.commandType.addEventListener("change", refreshCommandPreset);
els.runEvaluateButton.addEventListener("click", runEvaluate);
els.visionModeButtons.forEach((button) => {
  button.addEventListener("click", () => setVisionMode(button.dataset.visionMode));
});
window.addEventListener("hashchange", () => setActivePage(getInitialPage(), false));
window.addEventListener("resize", () => {
  if (state.activePage === "monitor") redrawChartSoon();
});

setActivePage(state.activePage, false);
refreshCommandPreset();
refresh();
setInterval(refresh, 8000);
