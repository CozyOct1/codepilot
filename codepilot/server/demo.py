from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


router = APIRouter(prefix="/api/demo", tags=["demo"])


class DemoAskRequest(BaseModel):
    repo_id: str = "codepilot"
    question: str


class DemoTaskRequest(BaseModel):
    repo_id: str = "codepilot"
    prompt: str
    scenario: str = "architecture"


DEMO_REPOS: list[dict[str, Any]] = [
    {
        "id": "codepilot",
        "name": "CodePilot",
        "description": "FastAPI + LangGraph + Chroma + SQLite 的私有代码仓库智能开发助手",
        "status": "ready",
        "indexed_files": 42,
        "safe_mode": True,
        "default_prompts": [
            "请分析这个仓库的整体架构，并说明主要模块作用。",
            "请分析 POST /api/tasks 接口从请求进入到数据库写入的完整流程。",
            "请说明 Prometheus 指标在哪里暴露，以及可以监控哪些信息。",
            "请为任务接口增加参数校验，并生成 Patch Preview。",
        ],
    },
    {
        "id": "fastapi-todo",
        "name": "FastAPI Todo Demo",
        "description": "用于展示接口链路分析、参数校验和测试建议的示例仓库",
        "status": "ready",
        "indexed_files": 18,
        "safe_mode": True,
        "default_prompts": [
            "帮我找出 Todo 创建接口的实现位置。",
            "请总结这个项目的测试覆盖情况。",
        ],
    },
    {
        "id": "vue-admin",
        "name": "Vue Admin Demo",
        "description": "用于展示前端路由、组件结构和 API 调用定位的示例仓库",
        "status": "ready",
        "indexed_files": 25,
        "safe_mode": True,
        "default_prompts": [
            "用户登录页面由哪些组件组成？",
            "请分析 API 请求封装在哪里。",
        ],
    },
]


RETRIEVAL_FIXTURES: dict[str, list[dict[str, Any]]] = {
    "codepilot": [
        {
            "path": "codepilot/server/main.py",
            "score": 0.91,
            "title": "FastAPI 入口与任务 API",
            "snippet": "post_task 接收 CreateTaskRequest，创建任务后可调用 run_agent_task 执行 LangGraph Agent。",
        },
        {
            "path": "codepilot/agent/graph.py",
            "score": 0.88,
            "title": "LangGraph Agent 编排",
            "snippet": "执行流包含 retrieve、plan、execute 三个节点，串联仓库检索、记忆注入、计划生成和 ReAct 工具调用。",
        },
        {
            "path": "codepilot/indexer/repo.py",
            "score": 0.84,
            "title": "Chroma 仓库索引",
            "snippet": "index_repository 遍历文本文件并写入 Chroma，search_repository 返回 Top-K 相关代码片段。",
        },
        {
            "path": "codepilot/tools/safety.py",
            "score": 0.79,
            "title": "安全工具边界",
            "snippet": "Shell 工具通过允许列表和高风险 token 拦截控制 Agent 可执行命令范围。",
        },
    ],
    "fastapi-todo": [
        {
            "path": "app/api/todos.py",
            "score": 0.89,
            "title": "Todo 创建接口",
            "snippet": "create_todo 负责参数校验、调用 service 层并返回持久化后的 Todo 对象。",
        },
        {
            "path": "app/services/todos.py",
            "score": 0.82,
            "title": "业务服务层",
            "snippet": "TodoService 将请求模型转换为数据库模型，并处理列表查询和状态更新。",
        },
    ],
    "vue-admin": [
        {
            "path": "src/router/index.ts",
            "score": 0.87,
            "title": "前端路由",
            "snippet": "路由表定义登录页、仪表盘和用户管理页面，并通过 meta 字段控制鉴权。",
        },
        {
            "path": "src/api/http.ts",
            "score": 0.83,
            "title": "请求封装",
            "snippet": "Axios 实例统一注入 token，并在响应拦截器中处理登录过期和错误提示。",
        },
    ],
}


TRACE_STEPS: list[dict[str, Any]] = [
    {
        "phase": "Thought",
        "title": "理解任务",
        "content": "用户希望了解任务接口的完整链路，需要先定位 API 入口、数据库写入和 Agent 执行节点。",
        "latency_ms": 42,
    },
    {
        "phase": "Action",
        "title": "repo_search",
        "content": 'query="POST /api/tasks create_task run_agent_task"',
        "latency_ms": 96,
    },
    {
        "phase": "Observation",
        "title": "召回代码上下文",
        "content": "命中 codepilot/server/main.py、codepilot/core/database.py、codepilot/agent/graph.py。",
        "latency_ms": 18,
    },
    {
        "phase": "Action",
        "title": "read_file",
        "content": "读取 FastAPI 路由、Task 模型和 LangGraph 执行流相关片段。",
        "latency_ms": 74,
    },
    {
        "phase": "Observation",
        "title": "分析调用链",
        "content": "请求进入 post_task 后写入 SQLite；run=true 时进入 retrieve -> plan -> execute；最终更新任务状态与结果摘要。",
        "latency_ms": 23,
    },
    {
        "phase": "Final",
        "title": "生成总结",
        "content": "POST /api/tasks 的核心链路是请求校验、任务持久化、Agent 执行、结果回写和指标记录。",
        "latency_ms": 61,
    },
]


PATCH_PREVIEW = """diff --git a/codepilot/server/schemas.py b/codepilot/server/schemas.py
@@
 class CreateTaskRequest(BaseModel):
     repo_path: str | None = None
-    user_request: str
+    user_request: str = Field(min_length=2, max_length=4000)
     session_id: str | None = None
     run: bool = True
"""


def _repo_or_404(repo_id: str) -> dict[str, Any]:
    for repo in DEMO_REPOS:
        if repo["id"] == repo_id:
            return repo
    raise HTTPException(status_code=404, detail="demo repo not found")


def _task_response(task_id: str, repo_id: str, prompt: str, scenario: str) -> dict[str, Any]:
    return {
        "id": task_id,
        "repo_id": repo_id,
        "prompt": prompt,
        "scenario": scenario,
        "mode": "Demo Mode: read-only safe execution",
        "status": "completed",
        "summary": "已完成只读演示链路：检索仓库上下文、展示 ReAct 轨迹、记录工具调用，并生成结果摘要。",
        "trace": TRACE_STEPS,
        "tools": [
            {"name": "repo_search", "status": "allowed", "latency_ms": 96},
            {"name": "read_file", "status": "allowed", "latency_ms": 74},
            {"name": "git_diff", "status": "preview_only", "latency_ms": 31},
            {"name": "shell", "status": "blocked_in_demo", "latency_ms": 0},
        ],
        "diff": PATCH_PREVIEW if "patch" in prompt.lower() or "参数校验" in prompt else "",
    }


@router.get("/repos")
def demo_repos() -> list[dict[str, Any]]:
    return DEMO_REPOS


@router.post("/ask")
def demo_ask(req: DemoAskRequest) -> dict[str, Any]:
    repo = _repo_or_404(req.repo_id)
    items = RETRIEVAL_FIXTURES.get(repo["id"], RETRIEVAL_FIXTURES["codepilot"])
    return {
        "repo": repo,
        "question": req.question,
        "results": items,
        "answer": (
            "根据当前 Top-K 召回结果，任务链路主要集中在 FastAPI 路由、数据库持久化、"
            "LangGraph Agent 编排和安全工具层。公网 Demo 仅展示只读检索和轨迹，不执行真实写操作。"
        ),
    }


@router.post("/tasks")
def demo_task(req: DemoTaskRequest) -> dict[str, Any]:
    _repo_or_404(req.repo_id)
    task_id = f"demo-{uuid.uuid4().hex[:10]}"
    return _task_response(task_id, req.repo_id, req.prompt, req.scenario)


@router.get("/tasks/{task_id}/trace")
def demo_trace(task_id: str) -> dict[str, Any]:
    return _task_response(task_id, "codepilot", "请分析 POST /api/tasks 接口链路", "api-flow")


@router.get("/tasks/{task_id}/diff")
def demo_diff(task_id: str) -> dict[str, str]:
    return {"task_id": task_id, "mode": "patch_preview", "diff": PATCH_PREVIEW}


@router.get("/metrics-summary")
def demo_metrics_summary() -> dict[str, Any]:
    return {
        "benchmarks": [
            {"label": "GET /health", "concurrency": 50, "qps": 261.16, "p95_ms": 222},
            {"label": "POST /api/tasks", "concurrency": 20, "qps": 146.09, "p95_ms": 668},
            {"label": "Task success rate", "concurrency": 20, "qps": 100.0, "p95_ms": 0},
        ],
        "signals": [
            "接口请求量",
            "任务创建成功率",
            "Agent 执行耗时",
            "工具调用次数",
            "SQLite 写入耗时",
            "错误率",
        ],
    }


@router.get("/tasks/{task_id}/events")
async def demo_events(task_id: str) -> StreamingResponse:
    async def event_stream():
        for index, step in enumerate(TRACE_STEPS, start=1):
            payload = {"task_id": task_id, "index": index, "timestamp": time.time(), **step}
            yield f"event: trace\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.25)
        yield (
            "event: done\n"
            f"data: {json.dumps({'task_id': task_id, 'status': 'completed'}, ensure_ascii=False)}\n\n"
        )

    return StreamingResponse(event_stream(), media_type="text/event-stream")
