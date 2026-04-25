from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from codepilot.tools.git import diff, status
from codepilot.tools.shell import run_command


@dataclass(frozen=True)
class ReactStep:
    thought: str
    action: str
    observation: str


def select_actions(user_request: str) -> list[str]:
    lower = user_request.lower()
    actions = ["git_status"]
    if any(token in lower for token in ["test", "pytest", "测试"]):
        actions.append("run_tests")
    if any(token in lower for token in ["diff", "差异", "变更"]):
        actions.append("git_diff")
    actions.append("finish")
    return actions


def run_react_loop(repo_path: Path, user_request: str, test_command: str = "uv run pytest") -> list[ReactStep]:
    steps: list[ReactStep] = []
    for action in select_actions(user_request):
        if action == "git_status":
            result = status(repo_path)
            steps.append(
                ReactStep(
                    thought="先观察仓库状态，确认当前工作区是否存在未提交变更。",
                    action="git_status",
                    observation=str(result.get("stdout", ""))[:4000] or "No status output.",
                )
            )
        elif action == "run_tests":
            result = run_command(repo_path, test_command, timeout=120)
            steps.append(
                ReactStep(
                    thought="用户请求涉及测试，执行默认测试命令并记录退出码和输出。",
                    action=test_command,
                    observation=(
                        f"Exit code: {result['exit_code']}\n"
                        f"STDOUT:\n{result['stdout']}\n"
                        f"STDERR:\n{result['stderr']}"
                    )[:8000],
                )
            )
        elif action == "git_diff":
            result = diff(repo_path)
            steps.append(
                ReactStep(
                    thought="用户请求涉及变更或差异，读取 Git Diff 作为观察结果。",
                    action="git_diff",
                    observation=str(result.get("stdout", ""))[:8000] or "No diff.",
                )
            )
        elif action == "finish":
            steps.append(
                ReactStep(
                    thought="已有观察足够生成结果摘要。",
                    action="finish",
                    observation="ReAct loop completed.",
                )
            )
    return steps


def format_react_trace(steps: list[ReactStep]) -> str:
    parts = []
    for index, step in enumerate(steps, start=1):
        parts.append(
            f"Step {index}\n"
            f"Thought: {step.thought}\n"
            f"Action: {step.action}\n"
            f"Observation:\n{step.observation}"
        )
    return "\n\n".join(parts)
