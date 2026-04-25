const state = {
  repos: [],
  activeRepo: null,
  latestTask: null,
};

const healthDot = document.querySelector("#health-dot");
const healthText = document.querySelector("#health-text");
const repoSelect = document.querySelector("#repo-select");
const repoSummary = document.querySelector("#repo-summary");
const taskInput = document.querySelector("#task-input");
const promptButtons = document.querySelector("#prompt-buttons");
const runDemoButton = document.querySelector("#run-demo");
const taskStatus = document.querySelector("#task-status");
const liveTimeline = document.querySelector("#live-timeline");
const contextView = document.querySelector("#context-view");
const toolsView = document.querySelector("#tools-view");
const diffView = document.querySelector("#diff-view");
const searchForm = document.querySelector("#search-form");
const searchInput = document.querySelector("#search-input");
const retrievalResults = document.querySelector("#retrieval-results");
const traceSample = document.querySelector("#trace-sample");
const metricsGrid = document.querySelector("#metrics-grid");

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw new Error(data?.detail || text || response.statusText);
  }
  return data;
}

async function checkHealth() {
  try {
    const data = await requestJson("/health");
    healthDot.className = "dot ok";
    healthText.textContent = data.status || "ok";
  } catch {
    healthDot.className = "dot fail";
    healthText.textContent = "offline";
  }
}

function renderRepoOptions() {
  repoSelect.innerHTML = state.repos
    .map((repo) => `<option value="${repo.id}">${escapeHtml(repo.name)}</option>`)
    .join("");
  state.activeRepo = state.repos[0] || null;
  renderActiveRepo();
}

function renderActiveRepo() {
  const repo = state.activeRepo;
  if (!repo) {
    repoSummary.innerHTML = '<p class="muted">暂无示例仓库</p>';
    return;
  }
  repoSummary.innerHTML = `
    <strong>${escapeHtml(repo.name)}</strong>
    <p>${escapeHtml(repo.description)}</p>
    <div class="mini-tags">
      <span>${repo.indexed_files} indexed files</span>
      <span>${repo.safe_mode ? "Safe Demo Mode" : "Local Mode"}</span>
      <span>${repo.status}</span>
    </div>
  `;
  promptButtons.innerHTML = repo.default_prompts
    .map((prompt) => `<button type="button" class="prompt-chip">${escapeHtml(prompt)}</button>`)
    .join("");
  promptButtons.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      taskInput.value = button.textContent;
    });
  });
}

function traceItem(step, index) {
  return `
    <article class="trace-item ${step.phase.toLowerCase()}">
      <div class="trace-index">${index}</div>
      <div>
        <div class="trace-head">
          <span>${escapeHtml(step.phase)}</span>
          <strong>${escapeHtml(step.title)}</strong>
          <em>${step.latency_ms ?? 0}ms</em>
        </div>
        <p>${escapeHtml(step.content)}</p>
      </div>
    </article>
  `;
}

function renderTimeline(steps, target = liveTimeline) {
  if (!steps.length) {
    target.innerHTML = '<div class="empty-state">暂无轨迹</div>';
    return;
  }
  target.innerHTML = steps.map((step, index) => traceItem(step, index + 1)).join("");
}

function renderRetrieval(results) {
  retrievalResults.innerHTML = results
    .map(
      (item, index) => `
        <article class="retrieval-card">
          <div class="score">Top ${index + 1} · ${Math.round(item.score * 100)}%</div>
          <h3>${escapeHtml(item.title)}</h3>
          <code>${escapeHtml(item.path)}</code>
          <p>${escapeHtml(item.snippet)}</p>
        </article>
      `,
    )
    .join("");
}

function renderContext(results) {
  contextView.innerHTML = results
    .map(
      (item) => `
        <article class="context-hit">
          <div>
            <strong>${escapeHtml(item.path)}</strong>
            <span>${Math.round(item.score * 100)}%</span>
          </div>
          <p>${escapeHtml(item.snippet)}</p>
        </article>
      `,
    )
    .join("");
}

function renderTools(tools) {
  toolsView.innerHTML = tools
    .map(
      (tool) => `
        <div class="tool-row">
          <strong>${escapeHtml(tool.name)}</strong>
          <span class="tool-status ${escapeHtml(tool.status)}">${escapeHtml(tool.status)}</span>
          <em>${tool.latency_ms}ms</em>
        </div>
      `,
    )
    .join("");
}

async function loadRepos() {
  state.repos = await requestJson("/api/demo/repos");
  renderRepoOptions();
}

async function runRetrieval(question = searchInput.value.trim()) {
  const repoId = state.activeRepo?.id || "codepilot";
  const data = await requestJson("/api/demo/ask", {
    method: "POST",
    body: JSON.stringify({ repo_id: repoId, question: question || "项目结构分析" }),
  });
  renderRetrieval(data.results);
  renderContext(data.results);
  return data;
}

function streamTrace(taskId) {
  const events = new EventSource(`/api/demo/tasks/${taskId}/events`);
  const streamed = [];
  liveTimeline.innerHTML = "";
  events.addEventListener("trace", (event) => {
    streamed.push(JSON.parse(event.data));
    renderTimeline(streamed);
  });
  events.addEventListener("done", () => {
    taskStatus.textContent = "completed";
    events.close();
  });
  events.onerror = () => {
    taskStatus.textContent = "stream closed";
    events.close();
  };
}

async function runDemoTask() {
  const prompt = taskInput.value.trim();
  if (!prompt) {
    taskInput.focus();
    return;
  }
  runDemoButton.disabled = true;
  runDemoButton.textContent = "运行中...";
  taskStatus.textContent = "running";
  diffView.textContent = "";
  try {
    const task = await requestJson("/api/demo/tasks", {
      method: "POST",
      body: JSON.stringify({
        repo_id: state.activeRepo?.id || "codepilot",
        prompt,
        scenario: "online-demo",
      }),
    });
    state.latestTask = task;
    renderTools(task.tools);
    diffView.textContent = task.diff || "当前任务没有生成 Patch Preview。";
    await runRetrieval(prompt);
    streamTrace(task.id);
  } catch (error) {
    taskStatus.textContent = "failed";
    liveTimeline.innerHTML = `<div class="empty-state">任务失败：${escapeHtml(error.message)}</div>`;
  } finally {
    runDemoButton.disabled = false;
    runDemoButton.textContent = "运行 Demo 任务";
  }
}

function setupTabs() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".tab-view").forEach((item) => item.classList.remove("active"));
      tab.classList.add("active");
      document.querySelector(`#${tab.dataset.tab}-view`).classList.add("active");
    });
  });
}

async function loadTraceSample() {
  const data = await requestJson("/api/demo/tasks/demo-sample/trace");
  renderTimeline(data.trace, traceSample);
}

async function loadMetrics() {
  const data = await requestJson("/api/demo/metrics-summary");
  metricsGrid.innerHTML = data.benchmarks
    .map(
      (item) => `
        <article class="metric-card">
          <span>${escapeHtml(item.label)}</span>
          <strong>${item.label.includes("rate") ? `${item.qps}%` : item.qps}</strong>
          <p>${item.concurrency} 并发 · P95 ${item.p95_ms}ms</p>
        </article>
      `,
    )
    .join("");
}

repoSelect.addEventListener("change", async () => {
  state.activeRepo = state.repos.find((repo) => repo.id === repoSelect.value) || state.repos[0];
  renderActiveRepo();
  await runRetrieval();
});

runDemoButton.addEventListener("click", runDemoTask);

searchForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await runRetrieval();
});

async function init() {
  setupTabs();
  await Promise.all([checkHealth(), loadRepos(), loadTraceSample(), loadMetrics()]);
  await runRetrieval();
}

init();
