from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

from codepilot.tools.safety import ensure_inside_repo


ALLOWED_PREFIXES = {
    "pytest",
    "python",
    "uv",
    "ruff",
    "mypy",
    "git",
    "docker",
    "npm",
    "pnpm",
}

BLOCKED_TOKENS = {"sudo", "rm", "mkfs", "dd", "chmod", "chown", "curl", "wget"}


def run_command(repo_path: Path, command: str, cwd: str = ".", timeout: int = 60) -> dict[str, object]:
    workdir = ensure_inside_repo(repo_path, Path(cwd))
    parts = shlex.split(command)
    if not parts:
        raise ValueError("empty command")
    if parts[0] not in ALLOWED_PREFIXES:
        raise ValueError(f"command not allowed: {parts[0]}")
    if parts[0] == "python" and shutil.which("python") is None:
        parts[0] = sys.executable or "python3"
    if BLOCKED_TOKENS.intersection(parts):
        raise ValueError(f"blocked token in command: {command}")
    started = time.perf_counter()
    proc = subprocess.run(parts, cwd=workdir, text=True, capture_output=True, timeout=timeout, check=False)
    return {
        "exit_code": proc.returncode,
        "stdout": proc.stdout[-8000:],
        "stderr": proc.stderr[-8000:],
        "duration_ms": int((time.perf_counter() - started) * 1000),
    }
