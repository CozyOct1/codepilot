from __future__ import annotations

from pydantic import BaseModel


class CreateSessionRequest(BaseModel):
    repo_path: str
    title: str | None = None


class CreateTaskRequest(BaseModel):
    repo_path: str | None = None
    user_request: str
    session_id: str | None = None
    run: bool = True


class ChatRequest(BaseModel):
    message: str
    repo_path: str | None = None
    session_id: str | None = None


class TaskResponse(BaseModel):
    id: str
    status: str
    user_request: str
    plan: str | None = None
    result_summary: str | None = None
    error_message: str | None = None
