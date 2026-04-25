from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy import Engine
from sqlmodel import Session

from codepilot.agent.llm import get_llm_client
from codepilot.agent.memory import LongTermMemory, ShortTermMemory
from codepilot.agent.react import format_react_trace, run_react_loop
from codepilot.core.config import get_settings
from codepilot.core.database import Task, update_task
from codepilot.core.metrics import TASKS_TOTAL
from codepilot.indexer.repo import search_repository


class AgentState(TypedDict, total=False):
    task_id: str
    repo_path: str
    user_request: str
    context: list[dict[str, str]]
    long_term_memory: list[dict[str, str]]
    short_term_memory: str
    plan: str
    react_trace: str
    result_summary: str
    error_message: str


def retrieve(state: AgentState) -> AgentState:
    settings = get_settings(state["repo_path"])
    repo = Path(state["repo_path"])
    state["context"] = search_repository(repo, settings.chroma_path, state["user_request"], limit=5)
    state["long_term_memory"] = LongTermMemory(settings.memory_path, repo).search(state["user_request"], limit=4)
    short_memory = ShortTermMemory.load(
        settings.memory_path,
        window_size=settings.short_memory_window,
        max_chars=settings.short_memory_max_chars,
    )
    state["short_term_memory"] = short_memory.render()
    return state


def plan(state: AgentState) -> AgentState:
    settings = get_settings(state["repo_path"])
    context = "\n\n".join(f"FILE: {item['path']}\n{item['content'][:1200]}" for item in state.get("context", []))
    long_memory = "\n\n".join(
        f"TASK: {item.get('task_id', '')}\n{item.get('content', '')[:1200]}"
        for item in state.get("long_term_memory", [])
    )
    short_memory = state.get("short_term_memory", "")
    fallback = (
        "ReAct Plan:\n"
        "Thought: inspect repository context, short-term memory, and long-term memory before acting.\n"
        "Action candidates: git_status, run_tests when the request asks for tests, git_diff when the request asks for changes.\n"
        "Observation handling: summarize each tool result and persist useful outcomes back into memory.\n\n"
        f"Relevant files: {', '.join(item['path'] for item in state.get('context', [])) or 'none'}\n"
        f"Long-term memory hits: {len(state.get('long_term_memory', []))}\n"
        f"Short-term memory available: {'yes' if short_memory else 'no'}"
    )
    llm = get_llm_client(settings)
    if not llm.available:
        state["plan"] = fallback
        return state
    try:
        response = llm.invoke_text(
            "You are CodePilot. Produce a concise implementation plan. "
            "Use the ReAct pattern with Thought, Action, Observation, Final sections. "
            "Do not include secrets. Do not invent files or tool results.\n\n"
            f"Request:\n{state['user_request']}\n\n"
            f"Short-term memory:\n{short_memory or 'none'}\n\n"
            f"Long-term memory:\n{long_memory or 'none'}\n\n"
            f"Repository context:\n{context or 'none'}"
        )
        state["plan"] = response or fallback
    except Exception as exc:
        state["plan"] = fallback + f"\n\nLLM planning unavailable: {exc}"
    return state


def execute(state: AgentState) -> AgentState:
    repo = Path(state["repo_path"])
    steps = run_react_loop(repo, state["user_request"])
    trace = format_react_trace(steps)
    state["react_trace"] = trace
    state["result_summary"] = (
        "ReAct execution trace:\n\n"
        f"{trace}\n\n"
        "Final: task completed with the available safe tools. "
        "Use a concrete edit request when code changes are required."
    )
    settings = get_settings(repo)
    short_memory = ShortTermMemory.load(
        settings.memory_path,
        window_size=settings.short_memory_window,
        max_chars=settings.short_memory_max_chars,
    )
    short_memory.add_turn("user", state["user_request"])
    short_memory.add_turn("assistant", state["result_summary"])
    short_memory.save()
    LongTermMemory(settings.memory_path, repo).add(
        state["task_id"],
        state["user_request"],
        state["result_summary"],
    )
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
