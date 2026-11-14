import importlib
from pathlib import Path

import pytest

from agentops_mcp import store
from agentops_mcp import server


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "test.sqlite3")
    store.initialise()


def test_run_lifecycle_and_metrics():
    created = server.start_run("ResearchAgent", "Summarise public climate data")
    run_id = created["run_id"]

    server.log_tool_call(run_id, "search_web", 125.5, "success")
    server.log_tool_call(run_id, "fetch_page", 80, "failed", "HTTP 503")
    finished = server.finish_run(run_id, "success")

    assert finished["status"] == "success"
    report = server.get_run_report(run_id)
    assert report["summary"]["tool_call_count"] == 2
    assert report["summary"]["failed_tool_calls"] == 1

    metrics = server.get_metrics()
    assert metrics["total_runs"] == 1
    assert metrics["success_rate_percent"] == 100.0
    assert len(metrics["tools"]) == 2


def test_cannot_log_after_run_finishes():
    run_id = server.start_run("TestAgent", "Test task")["run_id"]
    server.finish_run(run_id, "success")
    with pytest.raises(ValueError):
        server.log_tool_call(run_id, "late_call", 1)


def test_cannot_finish_twice():
    run_id = server.start_run("TestAgent", "Test task")["run_id"]
    server.finish_run(run_id, "success")
    with pytest.raises(ValueError):
        server.finish_run(run_id, "success")


def test_rejects_invalid_status():
    with pytest.raises(ValueError):
        server.start_run("", "task")
    run_id = server.start_run("TestAgent", "Test task")["run_id"]
    with pytest.raises(ValueError):
        server.log_tool_call(run_id, "tool", 10, "unknown")


def test_list_runs_filter():
    first = server.start_run("AgentA", "Task A")["run_id"]
    second = server.start_run("AgentB", "Task B")["run_id"]
    server.finish_run(first, "failed", "Timeout")
    server.finish_run(second, "success")
    result = server.list_runs(status="failed")
    assert result["count"] == 1
    assert result["runs"][0]["run_id"] == first
