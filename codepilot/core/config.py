from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


DEFAULT_CONFIG = {
    "project_name": "codepilot-project",
    "language": "python",
    "default_test_command": "uv run pytest",
    "index_enabled": True,
    "approval_required": True,
}


@dataclass(frozen=True)
class Settings:
    repo_path: Path
    project_dir: Path
    database_url: str
    redis_url: str
    chroma_path: Path
    host: str
    port: int
    langsmith_tracing: str
    langsmith_project: str

    @property
    def database_path(self) -> Path:
        if self.database_url.startswith("sqlite:///"):
            return (self.repo_path / self.database_url.removeprefix("sqlite:///")).resolve()
        return self.repo_path / ".codepilot" / "codepilot.db"


def load_project_config(repo_path: Path) -> dict[str, Any]:
    config_path = repo_path / ".codepilot" / "config.yaml"
    if not config_path.exists():
        return {}
    return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}


def write_project_config(repo_path: Path, values: dict[str, Any] | None = None) -> Path:
    project_dir = repo_path / ".codepilot"
    project_dir.mkdir(parents=True, exist_ok=True)
    config = DEFAULT_CONFIG | {"repo_path": str(repo_path.resolve())}
    if values:
        config.update(values)
    config_path = project_dir / "config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8")
    (project_dir / "logs").mkdir(exist_ok=True)
    return config_path


def get_settings(repo_path: str | Path | None = None) -> Settings:
    root = Path(repo_path or os.getcwd()).resolve()
    load_dotenv(root / ".env")
    project_config = load_project_config(root)
    project_dir = root / ".codepilot"
    database_url = os.getenv("CODEPILOT_DATABASE_URL", "sqlite:///./.codepilot/codepilot.db")
    redis_url = os.getenv("CODEPILOT_REDIS_URL", "redis://localhost:6379/0")
    chroma_path = Path(os.getenv("CODEPILOT_CHROMA_PATH", "./storage/chroma"))
    if not chroma_path.is_absolute():
        chroma_path = root / chroma_path
    return Settings(
        repo_path=Path(project_config.get("repo_path", root)).resolve(),
        project_dir=project_dir,
        database_url=database_url,
        redis_url=redis_url,
        chroma_path=chroma_path.resolve(),
        host=os.getenv("CODEPILOT_HOST", "0.0.0.0"),
        port=int(os.getenv("CODEPILOT_PORT", "8001")),
        langsmith_tracing=os.getenv("LANGSMITH_TRACING", "false"),
        langsmith_project=os.getenv("LANGSMITH_PROJECT", "codepilot"),
    )
