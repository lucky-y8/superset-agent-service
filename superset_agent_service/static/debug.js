"use strict";

const STORAGE_KEY = "superset-agent-console-session-v2";
const CONFIG_KEY = "superset-agent-console-config-v1";
const DEFAULT_SUPERSET_BASE_URL = "http://localhost:9000";

const state = {
  socket: null,
  socketReady: false,
  running: false,
  currentRunId: null,
  currentAnswer: null,
  tools: [],
  activityCount: 0,
  activityEvents: [],
  runSummary: null,
  reconnectTimer: null,
  reconnectEnabled: true,
  socketConnectSeq: 0,
  agentToken: null,
  agentTokenExpiresAt: 0,
};

const elements = {
  agentForm: document.querySelector("#agent-form"),
  question: document.querySelector("#question"),
  sendAgent: document.querySelector("#send-agent"),
  messageList: document.querySelector("#message-list"),
  runState: document.querySelector("#run-state"),
  activityList: document.querySelector("#activity-list"),
  activityRunId: document.querySelector("#activity-run-id"),
  activityCount: document.querySelector("#activity-count"),
  summaryStatus: document.querySelector("#summary-status"),
  summaryDuration: document.querySelector("#summary-duration"),
  summaryTokens: document.querySelector("#summary-tokens"),
  summaryError: document.querySelector("#summary-error"),
  summaryMessage: document.querySelector("#summary-message"),
  refreshSummary: document.querySelector("#refresh-summary"),
  clearChat: document.querySelector("#clear-chat"),
  refreshToken: document.querySelector("#refresh-token"),
  agentBaseUrl: document.querySelector("#agent-base-url"),
  supersetBaseUrl: document.querySelector("#superset-base-url"),
  supersetCookie: document.querySelector("#superset-cookie"),
  mcpResult: document.querySelector("#mcp-result"),
  mcpServerSummary: document.querySelector("#mcp-server-summary"),
  toolCount: document.querySelector("#tool-count"),
  toolName: document.querySelector("#tool-name"),
  toolArguments: document.querySelector("#tool-arguments"),
  toolOptions: document.querySelector("#tool-options"),
  knowledgeFile: document.querySelector("#knowledge-file"),
  knowledgeQuery: document.querySelector("#knowledge-query"),
  knowledgeResult: document.querySelector("#knowledge-result"),
  documentCount: document.querySelector("#document-count"),
  memoryType: document.querySelector("#memory-type"),
  memoryJson: document.querySelector("#memory-json"),
  memoryResult: document.querySelector("#memory-result"),
  memoryCount: document.querySelector("#memory-count"),
  traceRunId: document.querySelector("#trace-run-id"),
  traceTimeline: document.querySelector("#trace-timeline"),
  traceUser: document.querySelector("#trace-user"),
  traceStatus: document.querySelector("#trace-status"),
  traceCount: document.querySelector("#trace-count"),
  traceQuestion: document.querySelector("#trace-question"),
  traceAnswer: document.querySelector("#trace-answer"),
  traceStartedAt: document.querySelector("#trace-started-at"),
  traceCompletedAt: document.querySelector("#trace-completed-at"),
  traceDuration: document.querySelector("#trace-duration"),
  traceTokens: document.querySelector("#trace-tokens"),
  traceError: document.querySelector("#trace-error"),
  toast: document.querySelector("#toast"),
};

const activityLabels = {
  run_started: ["开始运行", "已接收请求并创建运行记录"],
  plan: ["分析问题", "正在整理问题和上下文"],
  tools_discovered: ["发现工具", "已读取当前身份可用的 MCP 工具"],
  rag_retrieved: ["检索知识库", "已找到相关知识片段"],
  rag_failed: ["知识库检索失败", "RAG 检索出现错误"],
  memory_loaded: ["读取长期记忆", "已检索相似历史对话"],
  memory_written: ["写入长期记忆", "本轮对话已写入语义记忆"],
  memory_failed: ["记忆处理失败", "长期记忆读写出现错误"],
  tool_plan: ["规划工具", "模型已选择下一步工具"],
  tool_started: ["执行工具", "正在调用 Superset MCP"],
  tool_completed: ["工具完成", "MCP 已返回结果"],
  tool_failed: ["工具失败", "工具调用出现错误"],
  tool_blocked: ["工具被拦截", "PolicyGuard 拦截了工具调用"],
  sql_guard_rewritten: ["SQL 已改写", "SQLGuard 限制了查询范围"],
  answer_generated: ["生成回答", "模型已完成最终回答"],
  run_completed: ["运行完成", "本次 Agent 运行已结束"],
  run_failed: ["运行失败", "本次 Agent 运行未完成"],
};

function normalizeBaseUrl(value) {
  return String(value || "").trim().replace(/\/$/, "");
}

function getAgentBaseUrl() {
  const configured = normalizeBaseUrl(elements.agentBaseUrl.value);
  return configured || window.location.origin;
}

function getSupersetBaseUrl() {
  return normalizeBaseUrl(elements.supersetBaseUrl.value) || DEFAULT_SUPERSET_BASE_URL;
}

function buildHttpUrl(baseUrl, path, agentToken) {
  const url = new URL(`${normalizeBaseUrl(baseUrl)}${path}`, window.location.origin);
  if (agentToken) {
    url.searchParams.set("agent_token", agentToken);
  }
  return url.toString();
}

function buildWebSocketUrl(baseUrl, path, agentToken) {
  const parsed = new URL(`${normalizeBaseUrl(baseUrl)}${path}`, window.location.origin);
  parsed.protocol = parsed.protocol === "https:" ? "wss:" : "ws:";
  if (agentToken) {
    parsed.searchParams.set("agent_token", agentToken);
  }
  return parsed.toString();
}

function extractAgentToken(payload) {
  return (
    payload?.token ||
    payload?.access_token ||
    payload?.result?.token ||
    payload?.result?.access_token ||
    ""
  );
}

async function getAgentToken(forceRefresh = false) {
  if (
    !forceRefresh &&
    state.agentToken &&
    state.agentTokenExpiresAt > Date.now()
  ) {
    return state.agentToken;
  }

  setConnectionState("token", false, "Token 获取中");
  const response = await fetch(
    buildHttpUrl(getAgentBaseUrl(), "/api/v1/agents/dev/superset-token"),
    {
    method: "POST",
    credentials: "include",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        superset_base_url: getSupersetBaseUrl(),
        cookie: elements.supersetCookie.value.trim(),
      }),
    },
  );
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();
  if (!response.ok) {
    const detail =
      typeof payload === "object" && payload !== null && "detail" in payload
        ? payload.detail
        : payload || `HTTP ${response.status}`;
    setConnectionState("token", false, "Token 获取失败");
    throw new Error(String(detail));
  }

  const token = extractAgentToken(payload);
  if (!token) {
    setConnectionState("token", false, "Token 响应无效");
    throw new Error("Superset token response does not include token");
  }
  const expiresIn = payload?.expires_in || payload?.result?.expires_in || 300;
  state.agentToken = token;
  state.agentTokenExpiresAt = Date.now() + Math.max(0, Number(expiresIn) * 1000 - 30000);
  setConnectionState("token", true, "Token 已获取");
  persistConfig();
  return token;
}

function addAgentTokenToBody(body, token) {
  if (typeof body !== "string") {
    return body;
  }
  try {
    const payload = JSON.parse(body);
    return JSON.stringify({
      ...payload,
      agent_token: token,
      token,
    });
  } catch {
    return body;
  }
}

async function agentFetch(path, options = {}) {
  const agentToken = await getAgentToken();
  const body = addAgentTokenToBody(options.body, agentToken);
  const headers = {
    ...(body instanceof FormData ? {} : body ? {"Content-Type": "application/json"} : {}),
    Authorization: `Bearer ${agentToken}`,
    "X-Superset-Agent-Token": agentToken,
    ...(options.headers || {}),
  };
  const response = await fetch(buildHttpUrl(getAgentBaseUrl(), path, agentToken), {
    credentials: "include",
    ...options,
    body,
    headers,
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();
  if (!response.ok) {
    const detail =
      typeof payload === "object" && payload !== null && "detail" in payload
        ? payload.detail
        : payload || `HTTP ${response.status}`;
    throw new Error(String(detail));
  }
  return payload;
}

function pretty(value) {
  return JSON.stringify(value, null, 2);
}

function formatDuration(milliseconds) {
  if (!Number.isFinite(milliseconds)) return "未记录";
  if (milliseconds < 1000) return `${milliseconds} ms`;
  return `${(milliseconds / 1000).toFixed(2)} s`;
}

function formatTokens(trace) {
  const total = trace?.total_tokens;
  if (!Number.isFinite(total)) return "未返回";
  const input = Number.isFinite(trace.input_tokens) ? trace.input_tokens : 0;
  const output = Number.isFinite(trace.output_tokens) ? trace.output_tokens : 0;
  return `${total} total | ${input} in / ${output} out`;
}

function formatDateTime(value) {
  return value ? new Date(value).toLocaleString() : "-";
}

function formatSummaryText(value, maxLength = 220) {
  if (!value) return "";
  const text = String(value).replace(/\s+/g, " ").trim();
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
}

function renderLiveSummary(trace, message = "") {
  state.runSummary = trace || null;
  const status = trace?.status || "等待";
  elements.summaryStatus.textContent = status;
  elements.summaryStatus.dataset.status = status;
  elements.summaryDuration.textContent = formatDuration(trace?.duration_ms);
  elements.summaryTokens.textContent = formatTokens(trace);
  elements.summaryError.textContent = formatSummaryText(trace?.error_message, 80) || "无";
  elements.summaryMessage.textContent = message || summaryMessageForTrace(trace);
}

function renderTraceSummary(trace) {
  elements.traceQuestion.textContent = formatSummaryText(trace?.question) || "-";
  elements.traceAnswer.textContent = formatSummaryText(trace?.final_answer) || "-";
  elements.traceStartedAt.textContent = formatDateTime(trace?.started_at);
  elements.traceCompletedAt.textContent = formatDateTime(trace?.completed_at);
  elements.traceDuration.textContent = formatDuration(trace?.duration_ms);
  elements.traceTokens.textContent = formatTokens(trace);
  elements.traceError.textContent = formatSummaryText(trace?.error_message) || "无";
}

function summaryMessageForTrace(trace) {
  if (!trace) return "发送请求后自动加载运行摘要。";
  if (trace.error_message) return "运行失败，错误详情已保存到 Run Trace。";
  if (trace.status === "completed") return "运行摘要已从持久化 Run Trace 加载。";
  if (trace.status === "running" || trace.status === "created") {
    return "运行中，完成后会自动刷新摘要。";
  }
  return "摘要已加载。";
}

async function refreshRunSummary(runId, showErrors = false) {
  if (!runId) {
    renderLiveSummary(null);
    return null;
  }
  renderLiveSummary(state.runSummary || {status: "loading"}, "正在读取运行摘要...");
  try {
    const trace = await agentFetch(`/api/v1/runs/${encodeURIComponent(runId)}`);
    renderLiveSummary(trace);
    persistSession();
    return trace;
  } catch (error) {
    renderLiveSummary(
      {status: "summary_error", error_message: error.message},
      "摘要加载失败。请确认数据库已执行 alembic upgrade head，并且服务使用同一个 DATABASE_URL。",
    );
    if (showErrors) showToast(error.message, true);
    return null;
  }
}

function parseJsonInput(element, label) {
  try {
    return JSON.parse(element.value || "{}");
  } catch (error) {
    throw new Error(`${label} 不是合法 JSON：${error.message}`);
  }
}

function showToast(message, isError = false) {
  elements.toast.textContent = message;
  elements.toast.classList.toggle("error", isError);
  elements.toast.classList.add("visible");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    elements.toast.classList.remove("visible");
  }, 3000);
}

function setConnectionState(kind, online, text) {
  const dot = document.querySelector(`#${kind}-status`);
  const label = document.querySelector(`#${kind}-status-text`);
  if (!dot || !label) return;
  dot.classList.toggle("online", online);
  dot.classList.toggle("offline", !online);
  label.textContent = text;
}

function activateView(viewId) {
  document.querySelectorAll(".nav-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === viewId);
  });
  document.querySelectorAll(".app-view").forEach((view) => {
    view.classList.toggle("active", view.id === viewId);
  });
}

async function connectSocket(forceRefreshToken = false) {
  window.clearTimeout(state.reconnectTimer);
  if (
    !forceRefreshToken &&
    state.socket &&
    [WebSocket.CONNECTING, WebSocket.OPEN].includes(state.socket.readyState)
  ) {
    return;
  }

  const connectSeq = state.socketConnectSeq + 1;
  state.socketConnectSeq = connectSeq;
  const previousSocket = state.socket;
  if (previousSocket && previousSocket.readyState !== WebSocket.CLOSED) {
    previousSocket.close(1000, "Replacing WebSocket connection");
  }

  let agentToken = "";
  try {
    agentToken = await getAgentToken(forceRefreshToken);
  } catch (error) {
    setConnectionState("socket", false, "实时通道 token 获取失败");
    showToast(error.message, true);
    state.reconnectTimer = window.setTimeout(() => connectSocket(false), 3000);
    return;
  }

  const socket = new WebSocket(
    buildWebSocketUrl(getAgentBaseUrl(), "/api/v1/agents/ws", agentToken),
  );
  state.socket = socket;

  socket.addEventListener("open", () => {
    if (connectSeq !== state.socketConnectSeq) return;
    state.socketReady = true;
    setConnectionState("socket", true, "实时通道在线");
  });

  socket.addEventListener("message", (event) => {
    if (connectSeq !== state.socketConnectSeq) return;
    handleSocketMessage(JSON.parse(event.data));
  });

  socket.addEventListener("close", () => {
    if (connectSeq !== state.socketConnectSeq) return;
    state.socketReady = false;
    setConnectionState("socket", false, "实时通道重连中");
    if (state.running) {
      failRun("实时连接已中断，请在连接恢复后重新发送。");
    }
    if (state.reconnectEnabled) {
      state.reconnectTimer = window.setTimeout(() => connectSocket(false), 1500);
    }
  });

  socket.addEventListener("error", () => {
    if (connectSeq !== state.socketConnectSeq) return;
    setConnectionState("socket", false, "实时通道异常");
  });
}

function handleSocketMessage(message) {
  if (message.type === "connected" || message.type === "authenticated") return;
  if (message.run_id) {
    state.currentRunId = message.run_id;
    elements.activityRunId.textContent = message.run_id;
    elements.traceRunId.value = message.run_id;
  }

  if (message.type === "run_event") {
    addActivity(message.event);
    if (["run_completed", "run_failed"].includes(message.event?.event_type) && message.run_id) {
      window.setTimeout(() => refreshRunSummary(message.run_id, true), 350);
    }
    return;
  }
  if (message.type === "answer_delta") {
    appendAnswerDelta(message.payload?.delta || "");
    return;
  }
  if (message.type === "final") {
    finishRun(message.response);
    return;
  }
  if (message.type === "error") {
    failRun(message.error || "Agent 运行失败");
  }
}

function buildRequest(agentToken) {
  return {
    type: "run",
    token: agentToken,
    agent_token: agentToken,
    access_token: agentToken,
    request: {
      question: elements.question.value.trim(),
      dashboard_id: document.querySelector("#dashboard-id").value.trim() || null,
      chart_id: document.querySelector("#chart-id").value.trim() || null,
      time_range: document.querySelector("#time-range").value.trim() || null,
      filters: parseJsonInput(document.querySelector("#filters"), "Filters"),
    },
  };
}

function startRun(question) {
  state.running = true;
  state.currentRunId = null;
  state.activityCount = 0;
  state.activityEvents = [];
  state.runSummary = null;
  elements.sendAgent.disabled = true;
  elements.runState.textContent = "运行中";
  elements.runState.className = "run-state running";
  elements.activityRunId.textContent = "正在创建运行";
  elements.activityCount.textContent = "0 步";
  elements.activityList.replaceChildren();
  renderLiveSummary({status: "running"}, "运行中，完成后自动加载摘要。");

  addMessage("user", question);
  state.currentAnswer = addMessage("assistant", "", true);
  persistSession();
  scrollConversation();
}

function addMessage(role, text, streaming = false) {
  const article = document.createElement("article");
  article.className = `message ${role}-message`;
  article.dataset.persisted = "true";
  article.dataset.role = role;

  if (role === "assistant") {
    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.textContent = "S";
    article.append(avatar);
  }

  const content = document.createElement("div");
  content.className = "message-content";
  if (role === "assistant") {
    const author = document.createElement("strong");
    author.textContent = "Superset Agent";
    content.append(author);
  }
  const textElement = document.createElement("div");
  textElement.className = "answer-text";
  textElement.classList.toggle("streaming", streaming);
  textElement.textContent = text;
  textElement.dataset.raw = text;
  content.append(textElement);
  article.append(content);
  elements.messageList.append(article);
  return textElement;
}

function appendAnswerDelta(delta) {
  if (!state.currentAnswer) {
    state.currentAnswer = addMessage("assistant", "", true);
  }
  state.currentAnswer.textContent += delta;
  state.currentAnswer.dataset.raw += delta;
  schedulePersist();
  scrollConversation();
}

function finishRun(response) {
  state.running = false;
  elements.sendAgent.disabled = false;
  elements.runState.textContent = "已完成";
  elements.runState.className = "run-state";
  elements.activityRunId.textContent = response.run_id;
  elements.traceRunId.value = response.run_id;

  if (state.currentAnswer) {
    state.currentAnswer.classList.remove("streaming");
    state.currentAnswer.dataset.raw = response.answer;
    renderMarkdown(state.currentAnswer, response.answer);
  }
  window.setTimeout(() => refreshRunSummary(response.run_id, true), 350);
  persistSession();
  showToast("Agent 运行完成");
}

function failRun(error) {
  state.running = false;
  elements.sendAgent.disabled = false;
  elements.runState.textContent = "失败";
  elements.runState.className = "run-state failed";
  if (state.currentAnswer) {
    state.currentAnswer.classList.remove("streaming");
    const message = `运行失败：${error}`;
    state.currentAnswer.textContent = message;
    state.currentAnswer.dataset.raw = message;
  }
  renderLiveSummary(
    {status: "failed", error_message: error},
    "运行失败，摘要会在 Run Trace 写入后自动刷新。",
  );
  persistSession();
  showToast(error, true);
}

function addActivity(event, shouldPersist = true) {
  const eventType = event.event_type;
  const [title, fallback] = activityLabels[eventType] || [eventType, "运行事件"];
  const payload = event.payload || {};
  const item = document.createElement("li");
  item.className = "activity-item";

  if (eventType.endsWith("_failed") || eventType === "tool_blocked") {
    item.classList.add("failed");
  } else if (eventType.endsWith("_completed") || eventType === "memory_written") {
    item.classList.add("done");
  } else {
    item.classList.add("active");
  }

  const heading = document.createElement("div");
  heading.className = "activity-title";
  const strong = document.createElement("strong");
  strong.textContent = title;
  const time = document.createElement("time");
  time.textContent = new Date(event.created_at).toLocaleTimeString();
  heading.append(strong, time);

  const detail = document.createElement("p");
  detail.className = "activity-detail";
  detail.textContent = activityDetail(eventType, payload, fallback);
  item.append(heading, detail);
  elements.activityList.append(item);

  state.activityCount += 1;
  if (shouldPersist) state.activityEvents.push(event);
  elements.activityCount.textContent = `${state.activityCount} 步`;
  elements.activityList.scrollTop = elements.activityList.scrollHeight;
  if (shouldPersist) persistSession();
}

function activityDetail(eventType, payload, fallback) {
  if (eventType === "tools_discovered") return `发现 ${payload.count || 0} 个可用工具`;
  if (eventType === "rag_retrieved") return `命中 ${payload.count || 0} 条知识`;
  if (eventType === "memory_loaded") return `命中 ${payload.semantic_conversation_count || 0} 条历史对话`;
  if (eventType === "memory_written") return `写入 ${payload.memory_type || "memory"}`;
  if (eventType === "tool_plan") return `计划调用：${(payload.tools || []).join(", ") || "未知工具"}`;
  if (eventType === "tool_started") return `${payload.tool || "工具"} ${pretty(payload.arguments || {})}`;
  if (eventType === "tool_completed") return `${payload.tool || "工具"} 已返回结果`;
  if (payload.error) return payload.error;
  return fallback;
}

function scrollConversation() {
  elements.messageList.scrollTop = elements.messageList.scrollHeight;
}

function renderMarkdown(container, markdown) {
  const lines = String(markdown || "").replace(/\r\n/g, "\n").split("\n");
  const fragment = document.createDocumentFragment();
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }
    if (line.startsWith("```")) {
      const language = line.slice(3).trim();
      const codeLines = [];
      index += 1;
      while (index < lines.length && !lines[index].startsWith("```")) {
        codeLines.push(lines[index]);
        index += 1;
      }
      index += index < lines.length ? 1 : 0;
      const pre = document.createElement("pre");
      const code = document.createElement("code");
      if (language) code.dataset.language = language;
      code.textContent = codeLines.join("\n");
      pre.append(code);
      fragment.append(pre);
      continue;
    }
    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      const element = document.createElement(`h${heading[1].length}`);
      appendInlineMarkdown(element, heading[2]);
      fragment.append(element);
      index += 1;
      continue;
    }
    if (line.includes("|") && index + 1 < lines.length && isTableSeparator(lines[index + 1])) {
      const tableLines = [line];
      index += 2;
      while (index < lines.length && lines[index].includes("|") && lines[index].trim()) {
        tableLines.push(lines[index]);
        index += 1;
      }
      fragment.append(buildMarkdownTable(tableLines));
      continue;
    }
    if (/^[-*+]\s+/.test(line)) {
      const list = document.createElement("ul");
      while (index < lines.length && /^[-*+]\s+/.test(lines[index])) {
        const item = document.createElement("li");
        appendInlineMarkdown(item, lines[index].replace(/^[-*+]\s+/, ""));
        list.append(item);
        index += 1;
      }
      fragment.append(list);
      continue;
    }
    if (/^\d+\.\s+/.test(line)) {
      const list = document.createElement("ol");
      while (index < lines.length && /^\d+\.\s+/.test(lines[index])) {
        const item = document.createElement("li");
        appendInlineMarkdown(item, lines[index].replace(/^\d+\.\s+/, ""));
        list.append(item);
        index += 1;
      }
      fragment.append(list);
      continue;
    }
    const paragraphLines = [line];
    index += 1;
    while (index < lines.length && lines[index].trim() && !startsMarkdownBlock(lines, index)) {
      paragraphLines.push(lines[index]);
      index += 1;
    }
    const paragraph = document.createElement("p");
    appendInlineMarkdown(paragraph, paragraphLines.join("\n"));
    fragment.append(paragraph);
  }
  container.replaceChildren(fragment);
  container.classList.add("markdown-body");
}

function startsMarkdownBlock(lines, index) {
  const line = lines[index];
  return (
    line.startsWith("```") ||
    /^(#{1,6})\s+/.test(line) ||
    /^[-*+]\s+/.test(line) ||
    /^\d+\.\s+/.test(line) ||
    (line.includes("|") && index + 1 < lines.length && isTableSeparator(lines[index + 1]))
  );
}

function isTableSeparator(line) {
  const cells = splitTableRow(line);
  return cells.length > 0 && cells.every((cell) => /^:?-{3,}:?$/.test(cell.trim()));
}

function splitTableRow(line) {
  return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim());
}

function buildMarkdownTable(lines) {
  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const tbody = document.createElement("tbody");
  const headerRow = document.createElement("tr");
  splitTableRow(lines[0]).forEach((cell) => {
    const header = document.createElement("th");
    appendInlineMarkdown(header, cell);
    headerRow.append(header);
  });
  thead.append(headerRow);
  lines.slice(1).forEach((line) => {
    const row = document.createElement("tr");
    splitTableRow(line).forEach((cell) => {
      const value = document.createElement("td");
      appendInlineMarkdown(value, cell);
      row.append(value);
    });
    tbody.append(row);
  });
  table.append(thead, tbody);
  const wrapper = document.createElement("div");
  wrapper.className = "markdown-table-wrap";
  wrapper.append(table);
  return wrapper;
}

function appendInlineMarkdown(parent, text) {
  const tokenPattern =
    /(`[^`\n]+`|\*\*[^*\n]+\*\*|__[^_\n]+__|\*[^*\n]+\*|_[^_\n]+_|\[[^\]\n]+\]\([^) \n]+\))/g;
  let cursor = 0;
  for (const match of text.matchAll(tokenPattern)) {
    appendTextWithBreaks(parent, text.slice(cursor, match.index));
    const token = match[0];
    if (token.startsWith("`")) {
      const code = document.createElement("code");
      code.textContent = token.slice(1, -1);
      parent.append(code);
    } else if (token.startsWith("**") || token.startsWith("__")) {
      const strong = document.createElement("strong");
      strong.textContent = token.slice(2, -2);
      parent.append(strong);
    } else if (token.startsWith("*") || token.startsWith("_")) {
      const emphasis = document.createElement("em");
      emphasis.textContent = token.slice(1, -1);
      parent.append(emphasis);
    } else if (token.startsWith("[")) {
      const linkMatch = token.match(/^\[([^\]]+)\]\(([^) \n]+)\)$/);
      if (linkMatch && /^https?:\/\//i.test(linkMatch[2])) {
        const link = document.createElement("a");
        link.textContent = linkMatch[1];
        link.href = linkMatch[2];
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        parent.append(link);
      } else {
        parent.append(document.createTextNode(token));
      }
    }
    cursor = match.index + token.length;
  }
  appendTextWithBreaks(parent, text.slice(cursor));
}

function appendTextWithBreaks(parent, text) {
  text.split("\n").forEach((part, index) => {
    if (index > 0) parent.append(document.createElement("br"));
    parent.append(document.createTextNode(part));
  });
}

function persistConfig() {
  try {
    localStorage.setItem(
      CONFIG_KEY,
      JSON.stringify({
        agentBaseUrl: elements.agentBaseUrl.value,
        supersetBaseUrl: elements.supersetBaseUrl.value,
        supersetCookie: elements.supersetCookie.value,
      }),
    );
  } catch (error) {
    console.warn("Unable to persist Agent config", error);
  }
}

function restoreConfig() {
  try {
    const saved = JSON.parse(localStorage.getItem(CONFIG_KEY) || "null");
    elements.agentBaseUrl.value = saved?.agentBaseUrl || window.location.origin;
    elements.supersetBaseUrl.value = saved?.supersetBaseUrl || DEFAULT_SUPERSET_BASE_URL;
    elements.supersetCookie.value = saved?.supersetCookie || "";
  } catch {
    elements.agentBaseUrl.value = window.location.origin;
    elements.supersetBaseUrl.value = DEFAULT_SUPERSET_BASE_URL;
  }
}

function persistSession() {
  try {
    const messages = Array.from(
      elements.messageList.querySelectorAll('.message[data-persisted="true"]'),
    ).map((message) => {
      const answer = message.querySelector(".answer-text");
      return {
        role: message.dataset.role,
        content: answer?.dataset.raw || answer?.textContent || "",
      };
    });
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        messages,
        activityEvents: state.activityEvents,
        runId: state.currentRunId,
        runState: elements.runState.textContent,
        runSummary: state.runSummary,
      }),
    );
  } catch (error) {
    console.warn("Unable to persist Agent session", error);
  }
}

function schedulePersist() {
  window.clearTimeout(schedulePersist.timer);
  schedulePersist.timer = window.setTimeout(persistSession, 250);
}

function restoreSession() {
  let saved;
  try {
    saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
  } catch (error) {
    console.warn("Unable to restore Agent session", error);
    return;
  }
  if (!saved || !Array.isArray(saved.messages)) return;
  saved.messages.forEach((message) => {
    if (!message || !["user", "assistant"].includes(message.role)) return;
    const answer = addMessage(message.role, message.content || "");
    if (message.role === "assistant") renderMarkdown(answer, message.content || "");
  });
  state.currentRunId = saved.runId || null;
  if (state.currentRunId) {
    elements.activityRunId.textContent = state.currentRunId;
    elements.traceRunId.value = state.currentRunId;
  }
  state.activityEvents = Array.isArray(saved.activityEvents) ? saved.activityEvents : [];
  if (state.activityEvents.length) {
    elements.activityList.replaceChildren();
    state.activityCount = 0;
    state.activityEvents.forEach((event) => addActivity(event, false));
  }
  if (saved.runState && saved.runState !== "运行中") elements.runState.textContent = saved.runState;
  if (saved.runSummary) renderLiveSummary(saved.runSummary);
  else if (state.currentRunId) refreshRunSummary(state.currentRunId, false);
  else renderLiveSummary(null);
  scrollConversation();
}

function clearConversation() {
  elements.messageList
    .querySelectorAll('.message[data-persisted="true"]')
    .forEach((message) => message.remove());
  state.currentRunId = null;
  state.currentAnswer = null;
  state.activityCount = 0;
  state.activityEvents = [];
  state.runSummary = null;
  elements.activityRunId.textContent = "等待运行";
  elements.activityCount.textContent = "0 步";
  elements.activityList.innerHTML = '<li class="activity-empty">发送请求后，执行步骤会实时显示在这里。</li>';
  elements.traceRunId.value = "";
  renderLiveSummary(null);
  renderTraceSummary(null);
  elements.runState.textContent = "空闲";
  elements.runState.className = "run-state";
  localStorage.removeItem(STORAGE_KEY);
  showToast("对话已清空");
}

async function submitAgent(event) {
  event.preventDefault();
  if (state.running) return;
  try {
    if (!state.socketReady || state.socket.readyState !== WebSocket.OPEN) {
      throw new Error("实时通道尚未连接，请稍后重试");
    }
    const agentToken = await getAgentToken();
    const message = buildRequest(agentToken);
    if (!message.request.question) throw new Error("请输入问题");
    startRun(message.request.question);
    state.socket.send(JSON.stringify(message));
  } catch (error) {
    failRun(error.message);
  }
}

async function refreshStatus() {
  persistConfig();
  const [agentCheck, mcpCheck] = await Promise.allSettled([
    agentFetch("/api/v1/health"),
    agentFetch("/api/v1/mcp/status"),
  ]);
  setConnectionState(
    "agent",
    agentCheck.status === "fulfilled",
    agentCheck.status === "fulfilled" ? "Agent 在线" : "Agent 离线",
  );
  if (mcpCheck.status === "fulfilled") {
    const status = mcpCheck.value;
    setConnectionState("mcp", true, `MCP 在线 · ${status.tool_count} tools`);
    elements.mcpServerSummary.textContent =
      `${status.server_name || "MCP Server"} ${status.server_version || ""} · ` +
      `${status.protocol_version || "unknown protocol"}`;
    elements.toolCount.textContent = `${status.tool_count} tools`;
  } else {
    setConnectionState("mcp", false, "MCP 离线");
    elements.mcpServerSummary.textContent = mcpCheck.reason?.message || "MCP 状态读取失败";
  }
}

async function loadTools() {
  try {
    elements.mcpResult.textContent = "正在读取工具列表...";
    const response = await agentFetch("/api/v1/mcp/tools");
    state.tools = response.tools || [];
    elements.toolCount.textContent = `${state.tools.length} tools`;
    elements.toolOptions.replaceChildren(
      ...state.tools.map((tool) => {
        const option = document.createElement("option");
        option.value = tool.name;
        option.label = tool.description;
        return option;
      }),
    );
    elements.mcpResult.textContent = pretty(response);
  } catch (error) {
    elements.mcpResult.textContent = error.message;
    showToast(error.message, true);
  }
}

function showSelectedToolSchema() {
  const tool = state.tools.find((item) => item.name === elements.toolName.value);
  if (tool) elements.mcpResult.textContent = pretty(tool);
}

async function callTool() {
  try {
    const name = elements.toolName.value.trim();
    if (!name) throw new Error("请输入 MCP 工具名称");
    const argumentsValue = parseJsonInput(elements.toolArguments, "Arguments");
    elements.mcpResult.textContent = "工具调用中...";
    const response = await agentFetch("/api/v1/mcp/call", {
      method: "POST",
      body: JSON.stringify({name, arguments: argumentsValue}),
    });
    elements.mcpResult.textContent = pretty(response);
  } catch (error) {
    elements.mcpResult.textContent = error.message;
    showToast(error.message, true);
  }
}

async function uploadDocument() {
  try {
    const file = elements.knowledgeFile.files?.[0];
    if (!file) throw new Error("请选择要上传的文件");
    const formData = new FormData();
    formData.append("file", file);
    elements.knowledgeResult.textContent = "上传并索引中...";
    const response = await agentFetch("/api/v1/rag/documents", {
      method: "POST",
      body: formData,
    });
    elements.knowledgeResult.textContent = pretty(response);
    await loadDocuments();
  } catch (error) {
    elements.knowledgeResult.textContent = error.message;
    showToast(error.message, true);
  }
}

async function loadDocuments() {
  try {
    const response = await agentFetch("/api/v1/rag/documents");
    elements.documentCount.textContent = `${response.length || 0} docs`;
    elements.knowledgeResult.textContent = pretty(response);
  } catch (error) {
    elements.knowledgeResult.textContent = error.message;
    showToast(error.message, true);
  }
}

async function searchKnowledge() {
  try {
    const query = elements.knowledgeQuery.value.trim();
    if (!query) throw new Error("请输入检索问题");
    const response = await agentFetch("/api/v1/rag/search", {
      method: "POST",
      body: JSON.stringify({query, limit: 5}),
    });
    elements.knowledgeResult.textContent = pretty(response);
  } catch (error) {
    elements.knowledgeResult.textContent = error.message;
    showToast(error.message, true);
  }
}

async function loadMemories() {
  try {
    const type = elements.memoryType.value.trim();
    const path = type
      ? `/api/v1/memories?memory_type=${encodeURIComponent(type)}`
      : "/api/v1/memories";
    const response = await agentFetch(path);
    elements.memoryCount.textContent = `${response.memories?.length || 0} items`;
    elements.memoryResult.textContent = pretty(response);
  } catch (error) {
    elements.memoryResult.textContent = error.message;
    showToast(error.message, true);
  }
}

async function saveMemory() {
  try {
    const payload = parseJsonInput(elements.memoryJson, "Memory JSON");
    const response = await agentFetch("/api/v1/memories", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    elements.memoryResult.textContent = pretty(response);
    await loadMemories();
  } catch (error) {
    elements.memoryResult.textContent = error.message;
    showToast(error.message, true);
  }
}

async function loadTrace() {
  const runId = elements.traceRunId.value.trim();
  if (!runId) {
    showToast("请输入 run_id", true);
    return;
  }
  try {
    const trace = await agentFetch(`/api/v1/runs/${encodeURIComponent(runId)}`);
    elements.traceUser.textContent = trace.user_id;
    elements.traceStatus.textContent = trace.status;
    elements.traceCount.textContent = trace.events.length;
    renderTraceSummary(trace);
    renderLiveSummary(trace);
    elements.traceTimeline.replaceChildren(
      ...trace.events.map((event) => {
        const item = document.createElement("li");
        item.className = "trace-item";
        const title = document.createElement("div");
        title.className = "trace-title";
        const type = document.createElement("strong");
        type.textContent = event.event_type;
        const time = document.createElement("time");
        time.textContent = new Date(event.created_at).toLocaleString();
        title.append(type, time);
        const payload = document.createElement("pre");
        payload.textContent = pretty(event.payload);
        item.append(title, payload);
        return item;
      }),
    );
  } catch (error) {
    showToast(error.message, true);
  }
}

function bindEvents() {
  document.querySelectorAll(".nav-button").forEach((button) => {
    button.addEventListener("click", () => activateView(button.dataset.view));
  });
  document.querySelector("#refresh-status").addEventListener("click", refreshStatus);
  elements.refreshToken.addEventListener("click", async () => {
    try {
      await getAgentToken(true);
      await connectSocket(true);
      showToast("Token 已刷新");
    } catch (error) {
      showToast(error.message, true);
    }
  });
  document.querySelector("#load-tools").addEventListener("click", loadTools);
  document.querySelector("#call-tool").addEventListener("click", callTool);
  document.querySelector("#upload-document").addEventListener("click", uploadDocument);
  document.querySelector("#load-documents").addEventListener("click", loadDocuments);
  document.querySelector("#search-knowledge").addEventListener("click", searchKnowledge);
  document.querySelector("#load-memories").addEventListener("click", loadMemories);
  document.querySelector("#save-memory").addEventListener("click", saveMemory);
  document.querySelector("#load-trace").addEventListener("click", loadTrace);
  elements.refreshSummary.addEventListener("click", () => {
    refreshRunSummary(state.currentRunId || elements.traceRunId.value.trim(), true);
  });
  elements.clearChat.addEventListener("click", clearConversation);
  elements.toolName.addEventListener("change", showSelectedToolSchema);
  elements.agentForm.addEventListener("submit", submitAgent);
  elements.question.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      elements.agentForm.requestSubmit();
    }
  });
  [elements.agentBaseUrl, elements.supersetBaseUrl, elements.supersetCookie].forEach((element) => {
    element.addEventListener("change", () => {
      state.agentToken = null;
      persistConfig();
      connectSocket(true);
    });
  });
}

restoreConfig();
restoreSession();
bindEvents();
connectSocket();
refreshStatus();
