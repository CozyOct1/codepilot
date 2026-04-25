from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from codepilot.tools.filesystem import list_dir, read_file, search_text, write_file
from codepilot.tools.git import diff, status
from codepilot.tools.shell import run_command

mcp = FastMCP("codepilot")


@mcp.tool()
def filesystem_list_dir(repo_path: str, path: str = ".") -> list[str]:
    return list_dir(Path(repo_path), path)


@mcp.tool()
def filesystem_read_file(repo_path: str, path: str) -> str:
    return read_file(Path(repo_path), path)


@mcp.tool()
def filesystem_write_file(repo_path: str, path: str, content: str) -> str:
    return str(write_file(Path(repo_path), path, content))


@mcp.tool()
def filesystem_search_text(repo_path: str, pattern: str) -> list[str]:
    return search_text(Path(repo_path), pattern)


@mcp.tool()
def shell_run_command(repo_path: str, command: str, cwd: str = ".", timeout: int = 60) -> dict[str, object]:
    return run_command(Path(repo_path), command, cwd=cwd, timeout=timeout)


@mcp.tool()
def git_status(repo_path: str) -> dict[str, object]:
    return status(Path(repo_path))


@mcp.tool()
def git_diff(repo_path: str) -> dict[str, object]:
    return diff(Path(repo_path))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
