from __future__ import annotations

from sqlmodel import Session

from codepilot.agent.graph import run_agent_task
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
    with Session(engine) as db:
        assert db.get(Task, task_id).status == "completed"
