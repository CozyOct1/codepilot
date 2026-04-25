const demoRepos = [
  {
    id: "codepilot",
    name: "CodePilot",
    description: "FastAPI + LangGraph + Chroma + SQLite 的私有代码仓库智能开发助手",
    status: "ready",
    indexed_files: 42,
    safe_mode: true,
    default_prompts: [
      "请分析这个仓库的整体架构，并说明主要模块作用。",
      "请分析 POST /api/tasks 接口从请求进入到数据库写入的完整流程。",
      "请说明 Prometheus 指标在哪里暴露，以及可以监控哪些信息。",
      "请为任务接口增加参数校验，并生成 Patch Preview。",
    ],
  },
  {
    id: "fastapi-todo",
    name: "FastAPI Todo Demo",
    description: "用于展示接口链路分析、参数校验和测试建议的示例仓库",
    status: "ready",
    indexed_files: 18,
    safe_mode: true,
    default_prompts: ["帮我找出 Todo 创建接口的实现位置。", "请总结这个项目的测试覆盖情况。"],
  },
  {
    id: "vue-admin",
    name: "Vue Admin Demo",
    description: "用于展示前端路由、组件结构和 API 调用定位的示例仓库",
    status: "ready",
    indexed_files: 25,
    safe_mode: true,
    default_prompts: ["用户登录页面由哪些组件组成？", "请分析 API 请求封装在哪里。"],
  },
];

const retrievalFixtures = {
  codepilot: [
    {
      path: "codepilot/server/main.py",
      score: 0.91,
      title: "FastAPI 入口与任务 API",
      snippet: "post_task 接收 CreateTaskRequest，创建任务后可调用 run_agent_task 执行 LangGraph Agent。",
    },
    {
      path: "codepilot/agent/graph.py",
      score: 0.88,
      title: "LangGraph Agent 编排",
      snippet: "执行流包含 retrieve、plan、execute 三个节点，串联仓库检索、记忆注入、计划生成和 ReAct 工具调用。",
    },
    {
      path: "codepilot/indexer/repo.py",
      score: 0.84,
      title: "Chroma 仓库索引",
      snippet: "index_repository 遍历文本文件并写入 Chroma，search_repository 返回 Top-K 相关代码片段。",
    },
    {
      path: "codepilot/tools/safety.py",
      score: 0.79,
      title: "安全工具边界",
      snippet: "Shell 工具通过允许列表和高风险 token 拦截控制 Agent 可执行命令范围。",
    },
  ],
  "fastapi-todo": [
    {
      path: "app/api/todos.py",
      score: 0.89,
      title: "Todo 创建接口",
      snippet: "create_todo 负责参数校验、调用 service 层并返回持久化后的 Todo 对象。",
    },
    {
      path: "app/services/todos.py",
      score: 0.82,
      title: "业务服务层",
      snippet: "TodoService 将请求模型转换为数据库模型，并处理列表查询和状态更新。",
    },
  ],
  "vue-admin": [
    {
      path: "src/router/index.ts",
      score: 0.87,
      title: "前端路由",
      snippet: "路由表定义登录页、仪表盘和用户管理页面，并通过 meta 字段控制鉴权。",
    },
    {
      path: "src/api/http.ts",
      score: 0.83,
      title: "请求封装",
      snippet: "Axios 实例统一注入 token，并在响应拦截器中处理登录过期和错误提示。",
    },
  ],
};

const traceSteps = [
  {
    phase: "Thought",
    title: "理解任务",
    content: "用户希望了解任务接口的完整链路，需要先定位 API 入口、数据库写入和 Agent 执行节点。",
    latency_ms: 42,
  },
  {
    phase: "Action",
    title: "repo_search",
    content: 'query="POST /api/tasks create_task run_agent_task"',
    latency_ms: 96,
  },
  {
    phase: "Observation",
    title: "召回代码上下文",
    content: "命中 codepilot/server/main.py、codepilot/core/database.py、codepilot/agent/graph.py。",
    latency_ms: 18,
  },
  {
    phase: "Action",
    title: "read_file",
    content: "读取 FastAPI 路由、Task 模型和 LangGraph 执行流相关片段。",
    latency_ms: 74,
  },
  {
    phase: "Observation",
    title: "分析调用链",
    content: "请求进入 post_task 后写入 SQLite；run=true 时进入 retrieve -> plan -> execute；最终更新任务状态与结果摘要。",
    latency_ms: 23,
  },
  {
    phase: "Final",
    title: "生成总结",
    content: "POST /api/tasks 的核心链路是请求校验、任务持久化、Agent 执行、结果回写和指标记录。",
    latency_ms: 61,
  },
];

const patchPreview = `diff --git a/codepilot/server/schemas.py b/codepilot/server/schemas.py
@@
 class CreateTaskRequest(BaseModel):
     repo_path: str | None = None
-    user_request: str
+    user_request: str = Field(min_length=2, max_length=4000)
     session_id: str | None = None
     run: bool = True
`;

const benchmarks = [
  { label: "GET /health", concurrency: 50, qps: 261.16, p95_ms: 222 },
  { label: "POST /api/tasks", concurrency: 20, qps: 146.09, p95_ms: 668 },
  { label: "Task success rate", concurrency: 20, qps: 100.0, p95_ms: 0 },
];

const state = {
  repos: demoRepos,
  activeRepo: demoRepos[0],
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

function renderRepoOptions() {
  repoSelect.innerHTML = state.repos
    .map((repo) => `<option value="${repo.id}">${escapeHtml(repo.name)}</option>`)
    .join("");
  renderActiveRepo();
}

function renderActiveRepo() {
  const repo = state.activeRepo;
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
  target.innerHTML = steps.length
    ? steps.map((step, index) => traceItem(step, index + 1)).join("")
    : '<div class="empty-state">暂无轨迹</div>';
}

function activeResults() {
  return retrievalFixtures[state.activeRepo?.id] || retrievalFixtures.codepilot;
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

function runRetrieval() {
  const results = activeResults();
  renderRetrieval(results);
  renderContext(results);
}

function streamTrace() {
  const streamed = [];
  liveTimeline.innerHTML = "";
  traceSteps.forEach((step, index) => {
    window.setTimeout(() => {
      streamed.push(step);
      renderTimeline(streamed);
      if (index === traceSteps.length - 1) {
        taskStatus.textContent = "completed";
      }
    }, index * 260);
  });
}

function runDemoTask() {
  const prompt = taskInput.value.trim();
  if (!prompt) {
    taskInput.focus();
    return;
  }
  runDemoButton.disabled = true;
  runDemoButton.textContent = "运行中...";
  taskStatus.textContent = "running";
  state.latestTask = `static-demo-${Date.now()}`;
  renderTools([
    { name: "repo_search", status: "allowed", latency_ms: 96 },
    { name: "read_file", status: "allowed", latency_ms: 74 },
    { name: "git_diff", status: "preview_only", latency_ms: 31 },
    { name: "shell", status: "blocked_in_demo", latency_ms: 0 },
  ]);
  diffView.textContent = prompt.includes("Patch") || prompt.includes("参数校验")
    ? patchPreview
    : "当前任务没有生成 Patch Preview。";
  runRetrieval();
  streamTrace();
  window.setTimeout(() => {
    runDemoButton.disabled = false;
    runDemoButton.textContent = "运行 Demo 任务";
  }, traceSteps.length * 260 + 120);
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

function loadMetrics() {
  metricsGrid.innerHTML = benchmarks
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

repoSelect.addEventListener("change", () => {
  state.activeRepo = state.repos.find((repo) => repo.id === repoSelect.value) || state.repos[0];
  renderActiveRepo();
  runRetrieval();
});

runDemoButton.addEventListener("click", runDemoTask);

searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  runRetrieval(searchInput.value.trim());
});

function init() {
  healthDot.className = "dot ok";
  healthText.textContent = "static demo";
  setupTabs();
  renderRepoOptions();
  runRetrieval();
  renderTimeline(traceSteps, traceSample);
  loadMetrics();
}

init();
