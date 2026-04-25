from __future__ import annotations

import os
from pathlib import Path
from typing import TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from sqlalchemy import Engine
from sqlmodel import Session

from codepilot.core.config import get_settings
from codepilot.core.database import Task, update_task
from codepilot.core.metrics import TASKS_TOTAL
from codepilot.indexer.repo import search_repository
from codepilot.tools.git import diff, status
from codepilot.tools.shell import run_command


class AgentState(TypedDict, total=False):
    task_id: str
    repo_path: str
    user_request: str
    context: list[dict[str, str]]
    plan: str
    result_summary: str
    error_message: str


def retrieve(state: AgentState) -> AgentState:
    settings = get_settings(state["repo_path"])
    state["context"] = search_repository(Path(state["repo_path"]), settings.chroma_path, state["user_request"], limit=5)
    return state


def plan(state: AgentState) -> AgentState:
    context = "\n\n".join(f"FILE: {item['path']}\n{item['content'][:1200]}" for item in state.get("context", []))
    fallback = (
        "Plan:\n"
        "1. Inspect retrieved repository context.\n"
        "2. Identify the files related to the request.\n"
        "3. Make minimal code changes with explicit user approval for destructive edits.\n"
        "4. Run the configured tests and summarize the result.\n\n"
        f"Relevant files:\n{', '.join(item['path'] for item in state.get('context', [])) or 'none'}"
    )
    if not os.getenv("OPENAI_API_KEY"):
        state["plan"] = fallback
        return state
    try:
        llm = ChatOpenAI(model=os.getenv("CODEPILOT_MODEL", "gpt-4o-mini"), timeout=30)
        message = llm.invoke(
            "You are CodePilot. Produce a concise implementation plan. "
            "Do not include secrets. Do not invent files.\n\n"
            f"Request:\n{state['user_request']}\n\nContext:\n{context}"
        )
        state["plan"] = str(message.content)
    except Exception as exc:
        state["plan"] = fallback + f"\n\nLLM planning unavailable: {exc}"
    return state


def execute(state: AgentState) -> AgentState:
    repo = Path(state["repo_path"])
    lower = state["user_request"].lower()
    summary_parts: list[str] = []
    summary_parts.append("Repository status:\n" + str(status(repo).get("stdout", "")))
    if any(token in lower for token in ["test", "pytest", "测试"]):
        result = run_command(repo, "uv run pytest", timeout=120)
        summary_parts.append(
            f"Test command exited {result['exit_code']}.\nSTDOUT:\n{result['stdout']}\nSTDERR:\n{result['stderr']}"
        )
    if any(token in lower for token in ["diff", "差异", "变更"]):
        summary_parts.append("Diff:\n" + str(diff(repo).get("stdout", "")))
    if not summary_parts:
        summary_parts.append("No mutating action was performed. Use a concrete edit request after reviewing the plan.")
    state["result_summary"] = "\n\n".join(summary_parts)
    return state


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("plan", plan)
    graph.add_node("execute", execute)
    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "plan")
    graph.add_edge("plan", "execute")
    graph.add_edge("execute", END)
    return graph.compile()


def run_agent_task(task_id: str, repo_path: Path, user_request: str, engine: Engine) -> Task:
    with Session(engine) as db:
        task = db.get(Task, task_id)
        if task is None:
            raise ValueError(f"task not found: {task_id}")
        update_task(db, task, status="running")
        try:
            state = build_graph().invoke(
                {"task_id": task_id, "repo_path": str(repo_path), "user_request": user_request}
            )
            task = db.get(Task, task_id)
            assert task is not None
            TASKS_TOTAL.labels(status="completed").inc()
            return update_task(
                db,
                task,
                status="completed",
                plan=state.get("plan"),
                result_summary=state.get("result_summary"),
            )
        except Exception as exc:
            task = db.get(Task, task_id)
            assert task is not None
            TASKS_TOTAL.labels(status="failed").inc()
            return update_task(db, task, status="failed", error_message=str(exc))
