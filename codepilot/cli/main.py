from __future__ import annotations

from pathlib import Path

import httpx
import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import Engine

from codepilot.agent.graph import run_agent_task
from codepilot.core.config import get_settings, write_project_config
from codepilot.core.database import create_db_engine, create_task, init_db, list_tasks
from codepilot.indexer.repo import index_repository
from codepilot.tools.git import commit as git_commit
from codepilot.tools.git import diff as git_diff
from codepilot.tools.shell import run_command

app = typer.Typer(help="CodePilot private repository coding agent.")
console = Console()


def engine_for(repo: Path) -> Engine:
    settings = get_settings(repo)
    engine = create_db_engine(settings)
    init_db(engine)
    return engine


@app.command()
def init(
    repo: Path = typer.Option(Path("."), "--repo", "-r", help="Repository path."),
    project_name: str | None = typer.Option(None, "--name", help="Project name."),
) -> None:
    repo = repo.resolve()
    config = write_project_config(repo, {"project_name": project_name or repo.name})
    engine_for(repo)
    console.print(f"Initialized CodePilot at [bold]{config}[/bold]")


@app.command()
def serve(
    host: str | None = typer.Option(None, "--host"),
    port: int | None = typer.Option(None, "--port"),
) -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "codepilot.server.main:app",
        host=host or settings.host,
        port=port or settings.port,
        reload=False,
        access_log=False,
    )


@app.command()
def index(repo: Path = typer.Option(Path("."), "--repo", "-r")) -> None:
    settings = get_settings(repo)
    result = index_repository(settings.repo_path, settings.chroma_path)
    console.print(result)


def run_local_task(request: str, repo: Path) -> None:
    engine = engine_for(repo)
    settings = get_settings(repo)
    from sqlmodel import Session

    with Session(engine) as db:
        task = create_task(db, settings.repo_path, request)
        task_id = task.id
    task = run_agent_task(task_id, settings.repo_path, request, engine)
    if task.plan:
        console.rule("Plan")
        console.print(task.plan)
    if task.result_summary:
        console.rule("Result")
        console.print(task.result_summary)
    if task.error_message:
        console.print(f"[red]{task.error_message}[/red]")


@app.command()
def ask(message: str, repo: Path = typer.Option(Path("."), "--repo", "-r")) -> None:
    run_local_task(message, repo.resolve())


@app.command()
def chat(repo: Path = typer.Option(Path("."), "--repo", "-r")) -> None:
    console.print("CodePilot chat. Type /exit to quit.")
    while True:
        message = typer.prompt("you")
        if message.strip() in {"/exit", "exit", "quit"}:
            return
        run_local_task(message, repo.resolve())


@app.command()
def edit(request: str, repo: Path = typer.Option(Path("."), "--repo", "-r")) -> None:
    run_local_task(request, repo.resolve())


@app.command(name="tasks")
def tasks_cmd(repo: Path = typer.Option(Path("."), "--repo", "-r"), limit: int = 20) -> None:
    engine = engine_for(repo.resolve())
    from sqlmodel import Session

    table = Table("ID", "Status", "Request", "Updated")
    with Session(engine) as db:
        for task in list_tasks(db, limit=limit):
            table.add_row(task.id[:8], task.status, task.user_request[:60], task.updated_at.isoformat())
    console.print(table)


@app.command()
def diff(repo: Path = typer.Option(Path("."), "--repo", "-r")) -> None:
    result = git_diff(repo.resolve())
    console.print(result["stdout"] or "No diff.")


@app.command()
def test(
    repo: Path = typer.Option(Path("."), "--repo", "-r"),
    command: str = typer.Option("uv run pytest", "--command", "-c"),
) -> None:
    result = run_command(repo.resolve(), command, timeout=180)
    console.print(result["stdout"])
    if result["stderr"]:
        console.print(f"[red]{result['stderr']}[/red]")
    raise typer.Exit(int(result["exit_code"]))


@app.command()
def commit(message: str, repo: Path = typer.Option(Path("."), "--repo", "-r")) -> None:
    result = git_commit(repo.resolve(), message)
    console.print(result["stdout"])
    if result["stderr"]:
        console.print(result["stderr"])
    raise typer.Exit(int(result["exit_code"]))


@app.command()
def remote(
    message: str,
    server: str = typer.Option("http://127.0.0.1:8001", "--server"),
    repo: Path = typer.Option(Path("."), "--repo", "-r"),
) -> None:
    response = httpx.post(
        f"{server.rstrip('/')}/api/tasks",
        json={"repo_path": str(repo.resolve()), "user_request": message, "run": True},
        timeout=300,
    )
    response.raise_for_status()
    console.print(response.json())


if __name__ == "__main__":
    app()
