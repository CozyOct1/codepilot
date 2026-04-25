from __future__ import annotations

from pathlib import Path

from codepilot.tools.shell import run_command


def status(repo_path: Path) -> dict[str, object]:
    return run_command(repo_path, "git status --short")


def diff(repo_path: Path) -> dict[str, object]:
    return run_command(repo_path, "git diff -- .")


def log(repo_path: Path, limit: int = 5) -> dict[str, object]:
    return run_command(repo_path, f"git log --oneline -{limit}")


def commit(repo_path: Path, message: str) -> dict[str, object]:
    run_command(repo_path, "git add .")
    return run_command(repo_path, f"git commit -m {message!r}")
