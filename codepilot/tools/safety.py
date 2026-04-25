from __future__ import annotations

from pathlib import Path


SENSITIVE_PARTS = {".ssh", ".gnupg", ".aws", ".config", "etc", "root"}


def ensure_inside_repo(repo_path: Path, target: Path) -> Path:
    repo = repo_path.resolve()
    resolved = (repo / target).resolve() if not target.is_absolute() else target.resolve()
    if repo != resolved and repo not in resolved.parents:
        raise ValueError(f"path escapes repo: {target}")
    if SENSITIVE_PARTS.intersection(resolved.parts):
        raise ValueError(f"sensitive path blocked: {target}")
    return resolved
