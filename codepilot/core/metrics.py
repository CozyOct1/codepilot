from __future__ import annotations

from prometheus_client import Counter, Histogram, generate_latest


TASKS_TOTAL = Counter("codepilot_tasks_total", "Total CodePilot tasks", ["status"])
TOOL_CALLS_TOTAL = Counter("codepilot_tool_calls_total", "Total tool calls", ["tool", "success"])
TOOL_LATENCY = Histogram("codepilot_tool_latency_seconds", "Tool call latency", ["tool"])


def metrics_response() -> bytes:
    return generate_latest()
