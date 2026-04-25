from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session

from codepilot.agent.graph import run_agent_task
from codepilot.core.config import get_settings
from codepilot.core.database import (
    SessionRecord,
    Task,
    create_db_engine,
    create_task,
    get_session,
    init_db,
    list_tasks,
)
from codepilot.core.metrics import metrics_response
from codepilot.indexer.repo import index_repository
from codepilot.server.schemas import ChatRequest, CreateSessionRequest, CreateTaskRequest

settings = get_settings()
engine = create_db_engine(settings)
init_db(engine)

app = FastAPI(title="CodePilot Agent Server", version="0.1.0")
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def db_session():
    yield from get_session(engine)


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(metrics_response(), media_type="text/plain; version=0.0.4")


@app.post("/api/sessions")
def create_session(req: CreateSessionRequest, db: Session = Depends(db_session)) -> SessionRecord:
    session = SessionRecord(repo_path=req.repo_path, title=req.title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@app.get("/api/tasks")
def tasks(limit: int = Query(20, ge=1, le=100), db: Session = Depends(db_session)):
    return list_tasks(db, limit=limit)


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str, db: Session = Depends(db_session)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@app.post("/api/tasks")
def post_task(req: CreateTaskRequest, db: Session = Depends(db_session)):
    repo = Path(req.repo_path or settings.repo_path).resolve()
    task = create_task(db, repo, req.user_request, req.session_id)
    if req.run:
        task = run_agent_task(task.id, repo, req.user_request, engine)
    return task


@app.post("/api/chat")
def chat(req: ChatRequest, db: Session = Depends(db_session)):
    repo = Path(req.repo_path or settings.repo_path).resolve()
    task = create_task(db, repo, req.message, req.session_id)
    task = run_agent_task(task.id, repo, req.message, engine)
    return task


@app.post("/api/index")
def index(repo_path: str | None = None):
    repo = Path(repo_path or settings.repo_path).resolve()
    result = index_repository(repo, settings.chroma_path)
    return result
