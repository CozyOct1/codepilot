from __future__ import annotations

from sqlmodel import Session

from codepilot.core.config import get_settings, write_project_config
from codepilot.core.database import create_db_engine, create_task, init_db, list_tasks


def test_init_config_and_database(tmp_path):
    config_path = write_project_config(tmp_path, {"project_name": "demo"})
    assert config_path.exists()

    settings = get_settings(tmp_path)
    engine = create_db_engine(settings)
    init_db(engine)

    with Session(engine) as db:
        task = create_task(db, tmp_path, "explain repo")
        assert task.status == "created"
        assert list_tasks(db)[0].id == task.id
