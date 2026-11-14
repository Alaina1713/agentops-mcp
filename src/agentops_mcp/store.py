"""Small SQLite persistence layer for AgentOps execution telemetry."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(os.getenv("AGENTOPS_DB_PATH", "./agentops.sqlite3")).expanduser()


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def initialise() -> None:
    with connect() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                agent_name TEXT NOT NULL,
                task TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('running','success','failed')),
                started_at TEXT NOT NULL,
                finished_at TEXT,
                duration_ms REAL,
                error TEXT
            );

            CREATE TABLE IF NOT EXISTS tool_calls (
                call_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
                tool_name TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('success','failed')),
                started_at TEXT NOT NULL,
                duration_ms REAL NOT NULL CHECK(duration_ms >= 0),
                error TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at DESC);
            CREATE INDEX IF NOT EXISTS idx_calls_run ON tool_calls(run_id);
        """)


def create_run(run_id: str, agent_name: str, task: str, started_at: str) -> None:
    with connect() as con:
        con.execute(
            """INSERT INTO runs(run_id, agent_name, task, status, started_at)
               VALUES (?, ?, ?, 'running', ?)""",
            (run_id, agent_name, task, started_at),
        )


def add_tool_call(
    run_id: str,
    tool_name: str,
    status: str,
    started_at: str,
    duration_ms: float,
    error: str | None,
) -> int:
    with connect() as con:
        cursor = con.execute(
            """INSERT INTO tool_calls
               (run_id, tool_name, status, started_at, duration_ms, error)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (run_id, tool_name, status, started_at, duration_ms, error),
        )
        return int(cursor.lastrowid)


def finish_run(
    run_id: str, status: str, finished_at: str, duration_ms: float, error: str | None
) -> bool:
    with connect() as con:
        cursor = con.execute(
            """UPDATE runs SET status=?, finished_at=?, duration_ms=?, error=?
               WHERE run_id=? AND status='running'""",
            (status, finished_at, duration_ms, error, run_id),
        )
        return cursor.rowcount == 1


def get_run(run_id: str) -> dict[str, Any] | None:
    with connect() as con:
        row = con.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            return None
        calls = con.execute(
            """SELECT call_id, tool_name, status, started_at, duration_ms, error
               FROM tool_calls WHERE run_id=? ORDER BY call_id""",
            (run_id,),
        ).fetchall()
        result = dict(row)
        result["tool_calls"] = [dict(call) for call in calls]
        return result


def list_runs(limit: int, status: str | None = None) -> list[dict[str, Any]]:
    with connect() as con:
        if status:
            rows = con.execute(
                """SELECT * FROM runs WHERE status=?
                   ORDER BY started_at DESC LIMIT ?""",
                (status, limit),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]


def metrics() -> dict[str, Any]:
    with connect() as con:
        totals = con.execute("""
            SELECT COUNT(*) AS total_runs,
                   SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS successful_runs,
                   SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed_runs,
                   AVG(duration_ms) AS average_duration_ms
            FROM runs WHERE status != 'running'
        """).fetchone()
        tools = con.execute("""
            SELECT tool_name,
                   COUNT(*) AS calls,
                   SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failures,
                   AVG(duration_ms) AS average_duration_ms
            FROM tool_calls
            GROUP BY tool_name
            ORDER BY calls DESC
        """).fetchall()
        total = totals["total_runs"] or 0
        successful = totals["successful_runs"] or 0
        return {
            "total_runs": total,
            "successful_runs": successful,
            "failed_runs": totals["failed_runs"] or 0,
            "success_rate_percent": round(successful / total * 100, 2) if total else 0.0,
            "average_duration_ms": (
                round(totals["average_duration_ms"], 2)
                if totals["average_duration_ms"] is not None else None
            ),
            "tools": [
                {
                    "tool_name": row["tool_name"],
                    "calls": row["calls"],
                    "failures": row["failures"],
                    "failure_rate_percent": round(row["failures"] / row["calls"] * 100, 2),
                    "average_duration_ms": round(row["average_duration_ms"], 2),
                }
                for row in tools
            ],
        }
