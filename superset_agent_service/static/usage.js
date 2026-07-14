const state = { days: 30 };
const byId = (id) => document.getElementById(id);
const formatNumber = (value) => new Intl.NumberFormat("zh-CN").format(value || 0);
const formatPercent = (value) => `${((value || 0) * 100).toFixed(1)}%`;
const formatDuration = (value) => value >= 1000 ? `${(value / 1000).toFixed(2)} s` : `${Math.round(value || 0)} ms`;

function headers() {
  const token = byId("agent-token").value.trim();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function loadDashboard() {
  byId("refresh").disabled = true;
  try {
    const response = await fetch(`/api/v1/usage/dashboard?days=${state.days}`, { headers: headers() });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || `Usage API 返回 ${response.status}`);
    }
    render(await response.json());
    byId("updated-at").textContent = `更新于 ${new Date().toLocaleTimeString()}`;
  } catch (error) {
    showToast(error.message, true);
  } finally {
    byId("refresh").disabled = false;
  }
}

function render(data) {
  const totals = data.totals;
  byId("total-runs").textContent = formatNumber(totals.total_runs);
  byId("run-breakdown").textContent = `${totals.completed_runs} 完成 / ${totals.failed_runs} 失败`;
  byId("success-rate").textContent = formatPercent(totals.success_rate);
  byId("avg-duration").textContent = formatDuration(totals.average_duration_ms);
  byId("total-tokens").textContent = formatNumber(totals.total_tokens);
  byId("total-cost").textContent = `$${Number(totals.total_cost_usd || 0).toFixed(4)}`;
  byId("eval-rate").textContent = formatPercent(totals.evaluation_pass_rate);
  byId("eval-breakdown").textContent = data.evaluations.total ? `${data.evaluations.passed} / ${data.evaluations.total} 通过` : "尚无评估";
  renderTrend(data.trend);
  renderTable("model-rows", data.models, (item) => [
    `${item.provider} / ${item.model}`, formatNumber(item.calls), formatNumber(item.tokens),
    formatDuration(item.average_latency_ms), formatNumber(item.failed_calls),
  ]);
  renderTable("tool-rows", data.tools, (item) => [item.tool, item.completed, item.failed, item.blocked]);
  renderErrors(data.errors);
  renderEvaluations(data.evaluations);
}

function renderTable(id, rows, mapRow) {
  const body = byId(id);
  body.replaceChildren();
  if (!rows.length) {
    const row = document.createElement("tr"); row.className = "empty-row";
    const cell = document.createElement("td"); cell.colSpan = 5; cell.textContent = "暂无数据";
    row.append(cell); body.append(row); return;
  }
  rows.forEach((item) => {
    const row = document.createElement("tr");
    mapRow(item).forEach((value) => { const cell = document.createElement("td"); cell.textContent = value; row.append(cell); });
    body.append(row);
  });
}

function renderErrors(errors) {
  const list = byId("error-list"); list.replaceChildren();
  if (!errors.length) { const item = document.createElement("li"); item.textContent = "当前周期没有失败运行"; list.append(item); return; }
  errors.forEach((error) => { const item = document.createElement("li"); const text = document.createElement("span"); text.textContent = error.message; text.title = error.message; const count = document.createElement("strong"); count.textContent = error.count; item.append(text, count); list.append(item); });
}

function renderEvaluations(value) {
  byId("eval-total").textContent = value.total;
  byId("eval-passed").textContent = value.passed;
  byId("eval-failed").textContent = value.failed;
  byId("eval-score").textContent = formatPercent(value.average_score);
  byId("evaluation-bar").style.width = formatPercent(value.pass_rate);
}

function renderTrend(points) {
  const canvas = byId("trend-chart"); const empty = byId("chart-empty");
  empty.style.display = points.length ? "none" : "grid";
  const rect = canvas.getBoundingClientRect(); const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, rect.width * ratio); canvas.height = Math.max(1, rect.height * ratio);
  const ctx = canvas.getContext("2d"); ctx.scale(ratio, ratio); ctx.clearRect(0, 0, rect.width, rect.height);
  if (!points.length) return;
  const pad = { left: 38, right: 12, top: 12, bottom: 28 }; const width = rect.width - pad.left - pad.right; const height = rect.height - pad.top - pad.bottom;
  const max = Math.max(1, ...points.map((point) => point.runs));
  ctx.strokeStyle = "#dfe5e8"; ctx.fillStyle = "#7c8a92"; ctx.font = "11px Segoe UI";
  for (let i = 0; i <= 4; i += 1) { const y = pad.top + height * i / 4; ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(rect.width - pad.right, y); ctx.stroke(); ctx.fillText(String(Math.round(max * (4 - i) / 4)), 4, y + 4); }
  const slot = width / points.length; const barWidth = Math.min(24, slot * 0.54);
  points.forEach((point, index) => { const x = pad.left + slot * index + (slot - barWidth) / 2; const runHeight = height * point.runs / max; const failHeight = height * point.failed / max; ctx.fillStyle = "#47b993"; ctx.fillRect(x, pad.top + height - runHeight, barWidth, runHeight); if (failHeight) { ctx.fillStyle = "#bd5753"; ctx.fillRect(x, pad.top + height - failHeight, barWidth, failHeight); } if (points.length <= 14 || index % Math.ceil(points.length / 10) === 0) { ctx.fillStyle = "#718089"; ctx.fillText(point.date.slice(5), x - 2, rect.height - 7); } });
}

function showToast(message, error = false) { const toast = byId("toast"); toast.textContent = message; toast.className = `toast visible${error ? " error" : ""}`; clearTimeout(showToast.timer); showToast.timer = setTimeout(() => { toast.className = "toast"; }, 3500); }

byId("agent-token").value = localStorage.getItem("usage-agent-token") || "";
byId("save-token").addEventListener("click", () => { localStorage.setItem("usage-agent-token", byId("agent-token").value.trim()); showToast("Token 已保存到当前浏览器"); loadDashboard(); });
byId("refresh").addEventListener("click", loadDashboard);
document.querySelectorAll("[data-days]").forEach((button) => button.addEventListener("click", () => { document.querySelectorAll("[data-days]").forEach((item) => item.classList.remove("active")); button.classList.add("active"); state.days = Number(button.dataset.days); loadDashboard(); }));
window.addEventListener("resize", () => { clearTimeout(window.usageResize); window.usageResize = setTimeout(loadDashboard, 180); });
loadDashboard();
