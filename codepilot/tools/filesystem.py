from __future__ import annotations

import hashlib
from pathlib import Path

from codepilot.tools.safety import ensure_inside_repo


MAX_READ_BYTES = 200_000


def list_dir(repo_path: Path, path: str = ".") -> list[str]:
    root = ensure_inside_repo(repo_path, Path(path))
    return sorted(p.name + ("/" if p.is_dir() else "") for p in root.iterdir())


def read_file(repo_path: Path, path: str, max_bytes: int = MAX_READ_BYTES) -> str:
    target = ensure_inside_repo(repo_path, Path(path))
    data = target.read_bytes()
    if len(data) > max_bytes:
        raise ValueError(f"file too large: {path}")
    return data.decode("utf-8", errors="replace")


def write_file(repo_path: Path, path: str, content: str) -> Path:
    target = ensure_inside_repo(repo_path, Path(path))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def get_file_hash(repo_path: Path, path: str) -> str:
    target = ensure_inside_repo(repo_path, Path(path))
    return hashlib.sha256(target.read_bytes()).hexdigest()


def search_text(repo_path: Path, pattern: str) -> list[str]:
    matches: list[str] = []
    for path in repo_path.rglob("*"):
        if path.is_dir() or any(part.startswith(".") for part in path.relative_to(repo_path).parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if pattern in text:
            matches.append(str(path.relative_to(repo_path)))
    return matches
