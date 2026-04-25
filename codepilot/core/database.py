from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Iterator

from sqlalchemy import Engine, event
from sqlmodel import Field, Session, SQLModel, create_engine, select

from codepilot.core.config import Settings


DB_WRITE_LOCK = RLock()


def new_id() -> str:
    return str(uuid.uuid4())


class SessionRecord(SQLModel, table=True):
    __tablename__ = "sessions"

    id: str = Field(default_factory=new_id, primary_key=True)
    repo_path: str
    title: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Message(SQLModel, table=True):
    __tablename__ = "messages"

    id: str = Field(default_factory=new_id, primary_key=True)
    session_id: str
    role: str
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Task(SQLModel, table=True):
    __tablename__ = "tasks"

    id: str = Field(default_factory=new_id, primary_key=True)
    session_id: str | None = None
    repo_path: str
    user_request: str
    status: str = "created"
    plan: str | None = None
    result_summary: str | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ToolCall(SQLModel, table=True):
    __tablename__ = "tool_calls"

    id: str = Field(default_factory=new_id, primary_key=True)
    task_id: str
    tool_name: str
    input_json: str | None = None
    output_json: str | None = None
    success: bool = False
    latency_ms: int | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FileChange(SQLModel, table=True):
    __tablename__ = "file_changes"

    id: str = Field(default_factory=new_id, primary_key=True)
    task_id: str
    file_path: str
    before_hash: str | None = None
    after_hash: str | None = None
    diff: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


def create_db_engine(settings: Settings) -> Engine:
    db_path = settings.database_path
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False, "timeout": 30},
        pool_size=20,
        max_overflow=40,
        pool_pre_ping=True,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.close()

    return engine


def init_db(engine: Engine) -> None:
    with DB_WRITE_LOCK:
        SQLModel.metadata.create_all(engine)


def get_session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as session:
        yield session


def create_task(db: Session, repo_path: Path, user_request: str, session_id: str | None = None) -> Task:
    task = Task(session_id=session_id, repo_path=str(repo_path), user_request=user_request)
    with DB_WRITE_LOCK:
        db.add(task)
        db.commit()
        db.refresh(task)
    return task


def update_task(db: Session, task: Task, **values: object) -> Task:
    for key, value in values.items():
        setattr(task, key, value)
    task.updated_at = datetime.utcnow()
    with DB_WRITE_LOCK:
        db.add(task)
        db.commit()
        db.refresh(task)
    return task


def list_tasks(db: Session, limit: int = 20) -> list[Task]:
    stmt = select(Task).order_by(Task.created_at.desc()).limit(limit)
    return list(db.exec(stmt))
