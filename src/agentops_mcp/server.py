"""AgentOps MCP server: lightweight observability for AI agent runs."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import time
import uuid
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import store

mcp = FastMCP(
    "AgentOps",
    instructions=(
        "AgentOps records AI-agent run metadata and tool-call telemetry. "
        "Start a run, log each tool invocation, finish the run, and inspect reports "
        "or aggregate metrics. Never send secrets or sensitive personal data as task "
        "descriptions or error messages."
    ),
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_text(value: str, field: str, max_length: int = 500) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field} cannot be empty")
    if len(cleaned) > max_length:
        raise ValueError(f"{field} must be {max_length} characters or fewer")
    return cleaned


@mcp.tool()
def start_run(agent_name: str, task: str) -> dict[str, Any]:
    """Start tracking an agent execution and return its unique run_id."""
    agent_name = _validate_text(agent_name, "agent_name", 100)
    task = _validate_text(task, "task", 500)
    run_id = str(uuid.uuid4())
    started_at = _now()
    store.create_run(run_id, agent_name, task, started_at)
    return {
        "run_id": run_id,
        "agent_name": agent_name,
        "status": "running",
        "started_at": started_at,
    }


@mcp.tool()
def log_tool_call(
    run_id: str,
    tool_name: str,
    duration_ms: float,
    status: str = "success",
    error: str = "",
) -> dict[str, Any]:
    """Record one tool invocation for a run, including latency and optional error.

    `status` must be 'success' or 'failed'. Keep error messages short and redact secrets.
    """
    tool_name = _validate_text(tool_name, "tool_name", 120)
    if status not in {"success", "failed"}:
        raise ValueError("status must be 'success' or 'failed'")
    if duration_ms < 0 or duration_ms > 86_400_000:
        raise ValueError("duration_ms must be between 0 and 86,400,000")
    run = store.get_run(run_id)
    if run is None:
        raise ValueError(f"Unknown run_id: {run_id}")
    if run["status"] != "running":
        raise ValueError("Cannot add tool calls to a completed run")
    error_text = _validate_text(error, "error", 500) if error.strip() else None
    if status == "failed" and error_text is None:
        error_text = "Unspecified tool failure"
    if status == "success":
        error_text = None

    call_id = store.add_tool_call(
        run_id, tool_name, status, _now(), float(duration_ms), error_text
    )
    return {
        "call_id": call_id,
        "run_id": run_id,
        "tool_name": tool_name,
        "status": status,
        "duration_ms": float(duration_ms),
    }


@mcp.tool()
def finish_run(run_id: str, status: str, error: str = "") -> dict[str, Any]:
    """Finish a tracked run with 'success' or 'failed' status."""
    if status not in {"success", "failed"}:
        raise ValueError("status must be 'success' or 'failed'")
    run = store.get_run(run_id)
    if run is None:
        raise ValueError(f"Unknown run_id: {run_id}")
    if run["status"] != "running":
        raise ValueError("Run has already been completed")
    finished_at = _now()
    started = datetime.fromisoformat(run["started_at"])
    finished = datetime.fromisoformat(finished_at)
    duration_ms = max(0.0, (finished - started).total_seconds() * 1000)
    error_text = _validate_text(error, "error", 500) if error.strip() else None
    if status == "failed" and error_text is None:
        error_text = "Run failed without a supplied error message"
    if status == "success":
        error_text = None
    updated = store.finish_run(run_id, status, finished_at, duration_ms, error_text)
    if not updated:
        raise ValueError("Run could not be completed; it may have changed concurrently")
    return {
        "run_id": run_id,
        "status": status,
        "finished_at": finished_at,
        "duration_ms": round(duration_ms, 2),
    }


@mcp.tool()
def get_run_report(run_id: str) -> dict[str, Any]:
    """Return one run with tool-call timeline and execution summary."""
    run = store.get_run(run_id)
    if run is None:
        raise ValueError(f"Unknown run_id: {run_id}")
    calls = run.pop("tool_calls")
    total_calls = len(calls)
    failed_calls = sum(call["status"] == "failed" for call in calls)
    run["summary"] = {
        "tool_call_count": total_calls,
        "failed_tool_calls": failed_calls,
        "tool_failure_rate_percent": (
            round(failed_calls / total_calls * 100, 2) if total_calls else 0.0
        ),
        "tool_latency_total_ms": round(sum(call["duration_ms"] for call in calls), 2),
    }
    run["tool_calls"] = calls
    return run


@mcp.tool()
def list_runs(limit: int = 20, status: str = "") -> dict[str, Any]:
    """List recent runs. Optional status filter: running, success, or failed."""
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    status_filter = status.strip() or None
    if status_filter and status_filter not in {"running", "success", "failed"}:
        raise ValueError("status must be running, success, failed, or empty")
    runs = store.list_runs(limit, status_filter)
    return {"count": len(runs), "runs": runs}


@mcp.tool()
def get_metrics() -> dict[str, Any]:
    """Return aggregate run success rate, average duration, and per-tool reliability."""
    return store.metrics()


@mcp.resource("agentops://about")
def about() -> str:
    """Explain AgentOps MCP capabilities."""
    return (
        "AgentOps MCP records agent runs and tool-call events in a local SQLite database. "
        "It reports run status, execution duration, tool latency, failure rates, and "
        "per-tool reliability metrics. Configure persistence with AGENTOPS_DB_PATH."
    )


def main() -> None:
    store.initialise()
    mcp.run()


if __name__ == "__main__":
    main()
