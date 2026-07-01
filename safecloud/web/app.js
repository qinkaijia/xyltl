const state = {
  apiBase: defaultApiBase(),
  summary: null,
  devices: [],
  alarms: [],
};

const els = {
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
};

els.apiBaseInput.value = state.apiBase;

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
  els.connectionBadge.classList.toggle("is-error", !ok && text !== "未连接");
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

function normalizeMetric(name, value) {
  const numeric = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numeric)) return 0;
  const scale = {
    temperature: 60,
    humidity: 100,
    gas: 500,
    smoke: 300,
    light: 1000,
    noise: 120,
    voltage: 300,
    current: 30,
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
  els.onlineRatio.textContent = total ? `${Math.round((online / total) * 100)}% 在线率` : "0%";
  els.metricNames.textContent = metrics.length ? metrics.slice(0, 4).join(" / ") : "暂无指标";
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
          <span class="metric-name">${metric.name}</span>
          <span class="metric-value">${formatValue(metric.value)}</span>
          <span class="metric-device">${metric.deviceId}</span>
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
    .map(
      (alarm) => `
        <div class="alarm-item">
          <div class="alarm-top">
            <span class="alarm-title">${alarm.metric_name || alarm.alarm_type}</span>
            <span class="pill ${alarm.alarm_level}">${alarm.alarm_level}</span>
          </div>
          <span>${alarm.alarm_message}</span>
          <span class="muted">${alarm.device_id} · ${formatTime(alarm.created_at)}</span>
        </div>
      `,
    )
    .join("");
}

function renderDevices() {
  const devices = state.devices || [];
  const counts = state.summary?.device_status || {};
  els.deviceStatusText.textContent = Object.entries(counts)
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
      return `
        <div class="device-item">
          <div class="device-top">
            <span class="device-title">${name}</span>
            <span class="pill ${device.status}">${device.status}</span>
          </div>
          <span class="muted">${device.device_id} · ${device.device_type}</span>
          <span>${location}</span>
          <span class="muted">last seen: ${formatTime(device.last_seen)}</span>
        </div>
      `;
    })
    .join("");

  const current = els.commandDevice.value;
  els.commandDevice.innerHTML = devices
    .map((device) => `<option value="${device.device_id}">${device.device_id}</option>`)
    .join("");
  if (current) els.commandDevice.value = current;
}

function drawChart(metrics) {
  const canvas = els.metricChart;
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#fbfcfb";
  ctx.fillRect(0, 0, width, height);

  if (!metrics.length) {
    ctx.fillStyle = "#65716a";
    ctx.font = "16px Segoe UI";
    ctx.fillText("暂无指标快照", 28, 52);
    return;
  }

  const padding = 34;
  const chartWidth = width - padding * 2;
  const barGap = 12;
  const barWidth = Math.max(22, (chartWidth - barGap * (metrics.length - 1)) / metrics.length);
  const baseline = height - 46;
  const maxHeight = height - 86;
  const palette = ["#1f7a85", "#20745a", "#b7791f", "#8a5a9e", "#bd3b3b"];

  ctx.strokeStyle = "#d8ded8";
  ctx.lineWidth = 1;
  for (let i = 0; i < 4; i += 1) {
    const y = 28 + i * (maxHeight / 3);
    ctx.beginPath();
    ctx.moveTo(padding, y);
    ctx.lineTo(width - padding, y);
    ctx.stroke();
  }

  metrics.forEach((metric, index) => {
    const x = padding + index * (barWidth + barGap);
    const normalized = normalizeMetric(metric.name, metric.value);
    const h = Math.max(4, normalized * maxHeight);
    const y = baseline - h;
    ctx.fillStyle = palette[index % palette.length];
    ctx.fillRect(x, y, barWidth, h);
    ctx.fillStyle = "#27312d";
    ctx.font = "bold 13px Segoe UI";
    ctx.fillText(formatValue(metric.value), x, y - 8);
    ctx.fillStyle = "#65716a";
    ctx.font = "12px Segoe UI";
    const label = metric.name.length > 10 ? `${metric.name.slice(0, 9)}…` : metric.name;
    ctx.fillText(label, x, baseline + 22);
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

els.refreshButton.addEventListener("click", refresh);
els.apiBaseInput.addEventListener("change", refresh);
els.loadAlarmsButton.addEventListener("click", loadAllAlarms);
els.commandForm.addEventListener("submit", submitCommand);

refresh();
setInterval(refresh, 8000);
