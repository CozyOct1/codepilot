from __future__ import annotations

from sqlmodel import Session

from codepilot.agent.llm import get_llm_client
from codepilot.agent.graph import run_agent_task
from codepilot.agent.memory import LongTermMemory, ShortTermMemory
from codepilot.core.config import get_settings, write_project_config
from codepilot.core.database import Task, create_db_engine, create_task, init_db
from codepilot.indexer.repo import index_repository, search_repository


def test_index_repository(tmp_path):
    (tmp_path / "README.md").write_text("CodePilot demo project", encoding="utf-8")
    settings = get_settings(tmp_path)
    result = index_repository(tmp_path, settings.chroma_path)
    assert result["indexed_files"] >= 1
    matches = search_repository(tmp_path, settings.chroma_path, "demo")
    assert matches


def test_agent_runs_offline(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("CODEPILOT_LLM_PROVIDER", "offline")
    write_project_config(tmp_path)
    (tmp_path / "README.md").write_text("Demo repository", encoding="utf-8")
    settings = get_settings(tmp_path)
    engine = create_db_engine(settings)
    init_db(engine)
    with Session(engine) as db:
        task = create_task(db, tmp_path, "请解释这个项目")
        task_id = task.id
    result = run_agent_task(task_id, tmp_path, "请解释这个项目", engine)
    assert result.status == "completed"
    assert result.plan
    assert "ReAct execution trace" in (result.result_summary or "")
    assert (settings.memory_path / "short_term.json").exists()
    assert LongTermMemory(settings.memory_path, tmp_path).search("Demo repository")
    with Session(engine) as db:
        assert db.get(Task, task_id).status == "completed"


def test_short_term_memory_compresses(tmp_path):
    memory = ShortTermMemory.load(tmp_path, window_size=2, max_chars=120)
    memory.add_turn("user", "first")
    memory.add_turn("assistant", "second")
    memory.add_turn("user", "third")
    memory.save()

    restored = ShortTermMemory.load(tmp_path, window_size=2, max_chars=120)
    assert len(restored.turns) == 2
    assert "first" in restored.summary
    assert "third" in restored.render()


def test_llm_client_supports_offline_and_openai_compatible(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEPILOT_LLM_PROVIDER", "offline")
    offline = get_llm_client(get_settings(tmp_path))
    assert not offline.available

    monkeypatch.setenv("CODEPILOT_LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    client = get_llm_client(get_settings(tmp_path))
    assert client.available
    assert client.provider == "deepseek"
    assert client.model == "deepseek-chat"
