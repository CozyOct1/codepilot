from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from codepilot.tools.safety import ensure_inside_repo


INSTRUCTION_FILES = (
    "CLAUDE.md",
    "AGENTS.md",
    "CODEPILOT.md",
    ".codepilot/instructions.md",
)
MAX_INSTRUCTION_BYTES = 64_000


@dataclass(frozen=True)
class ProjectInstruction:
    path: str
    content: str


def load_project_instructions(
    repo_path: Path,
    names: tuple[str, ...] = INSTRUCTION_FILES,
    max_bytes: int = MAX_INSTRUCTION_BYTES,
) -> list[ProjectInstruction]:
    """Load repository-local guidance files used to steer agent behavior."""
    instructions: list[ProjectInstruction] = []
    seen: set[Path] = set()
    for name in names:
        target = ensure_inside_repo(repo_path, Path(name))
        if target in seen or not target.is_file():
            continue
        seen.add(target)
        data = target.read_bytes()
        if len(data) > max_bytes:
            content = data[:max_bytes].decode("utf-8", errors="replace")
            content += "\n\n[truncated: project instruction file exceeded size limit]"
        else:
            content = data.decode("utf-8", errors="replace")
        instructions.append(ProjectInstruction(path=name, content=content.strip()))
    return instructions


def render_project_instructions(instructions: list[ProjectInstruction]) -> str:
    if not instructions:
        return ""
    return "\n\n".join(
        f"PROJECT INSTRUCTIONS: {instruction.path}\n{instruction.content}"
        for instruction in instructions
        if instruction.content
    )
