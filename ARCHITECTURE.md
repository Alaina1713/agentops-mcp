# Architecture and event lifecycle

Each tracked workflow has one `run_id`. Tool-call events are attached to that run.

1. `start_run` inserts a run with status `running`.
2. `log_tool_call` appends a tool event while the run remains active.
3. `finish_run` records the terminal status and elapsed wall-clock duration.
4. `get_run_report` combines run metadata and tool events.
5. `get_metrics` aggregates run and per-tool reliability statistics.

The MCP server is intentionally explicit: it does not monkey-patch or intercept agent
frameworks. An agent, middleware layer, or application wrapper reports events through
the MCP tools. This keeps the first version framework-independent.
