const state = {
  repoPath: "",
};

const healthDot = document.querySelector("#health-dot");
const healthText = document.querySelector("#health-text");
const serviceStatus = document.querySelector("#service-status");
const taskCount = document.querySelector("#task-count");
const completedCount = document.querySelector("#completed-count");
const failedCount = document.querySelector("#failed-count");
const taskTable = document.querySelector("#task-table");
const resultView = document.querySelector("#result-view");
const taskForm = document.querySelector("#task-form");
const repoPathInput = document.querySelector("#repo-path");
const taskRequestInput = document.querySelector("#task-request");
const runAgentInput = document.querySelector("#run-agent");
const indexButton = document.querySelector("#index-button");
const refreshButton = document.querySelector("#refresh-button");

function formatJson(value) {
  return JSON.stringify(value, null, 2);
}

function setResult(value) {
  resultView.textContent = typeof value === "string" ? value : formatJson(value);
}

function setBusy(button, busy) {
  button.disabled = busy;
  button.dataset.originalText = button.dataset.originalText || button.textContent;
  button.textContent = busy ? "处理中..." : button.dataset.originalText;
}

function normalizeDate(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function shortId(value) {
  return value ? value.slice(0, 8) : "-";
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
  let data = text;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!response.ok) {
    throw new Error(typeof data === "string" ? data : formatJson(data));
  }
  return data;
}

async function checkHealth() {
  try {
    const data = await requestJson("/health");
    healthDot.className = "dot ok";
    healthText.textContent = "服务正常";
    serviceStatus.textContent = data.status || "ok";
  } catch (error) {
    healthDot.className = "dot fail";
    healthText.textContent = "服务异常";
    serviceStatus.textContent = "fail";
  }
}

function renderTasks(tasks) {
  taskCount.textContent = String(tasks.length);
  completedCount.textContent = String(tasks.filter((task) => task.status === "completed").length);
  failedCount.textContent = String(tasks.filter((task) => task.status === "failed").length);

  if (!tasks.length) {
    taskTable.innerHTML = '<tr><td colspan="4">暂无数据</td></tr>';
    return;
  }

  taskTable.innerHTML = tasks
    .map((task) => {
      const status = task.status || "unknown";
      return `
        <tr>
          <td>${shortId(task.id)}</td>
          <td><span class="badge ${status}">${status}</span></td>
          <td>${escapeHtml(task.user_request || "")}</td>
          <td>${normalizeDate(task.updated_at)}</td>
        </tr>
      `;
    })
    .join("");
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function loadTasks() {
  const tasks = await requestJson("/api/tasks?limit=20");
  renderTasks(Array.isArray(tasks) ? tasks : []);
}

async function createTask(event) {
  event.preventDefault();
  const submitButton = taskForm.querySelector("button[type='submit']");
  const userRequest = taskRequestInput.value.trim();
  const repoPath = repoPathInput.value.trim();

  if (!userRequest) {
    setResult("请先填写任务描述。");
    taskRequestInput.focus();
    return;
  }

  const payload = {
    user_request: userRequest,
    run: runAgentInput.checked,
  };
  if (repoPath) {
    payload.repo_path = repoPath;
    state.repoPath = repoPath;
  }

  setBusy(submitButton, true);
  try {
    const task = await requestJson("/api/tasks", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setResult(task);
    await loadTasks();
  } catch (error) {
    setResult(`任务创建失败：\n${error.message}`);
  } finally {
    setBusy(submitButton, false);
  }
}

async function buildIndex() {
  const repoPath = repoPathInput.value.trim() || state.repoPath;
  const url = repoPath ? `/api/index?repo_path=${encodeURIComponent(repoPath)}` : "/api/index";
  setBusy(indexButton, true);
  try {
    const result = await requestJson(url, { method: "POST" });
    setResult(result);
  } catch (error) {
    setResult(`索引构建失败：\n${error.message}`);
  } finally {
    setBusy(indexButton, false);
  }
}

async function refreshAll() {
  setBusy(refreshButton, true);
  try {
    await Promise.all([checkHealth(), loadTasks()]);
  } catch (error) {
    setResult(`刷新失败：\n${error.message}`);
  } finally {
    setBusy(refreshButton, false);
  }
}

taskForm.addEventListener("submit", createTask);
indexButton.addEventListener("click", buildIndex);
refreshButton.addEventListener("click", refreshAll);

refreshAll();
