# AgentOps MCP

**An MCP server for tracing, monitoring, and analysing AI-agent executions.**

AgentOps MCP gives MCP-compatible AI assistants a lightweight observability layer. It records agent runs and tool invocations, then exposes execution reports and reliability metrics through structured MCP tools.

## The problem

As AI agents use more tools and perform longer workflows, it becomes difficult to answer basic operational questions:

- Which agent runs failed?
- Which tool calls are slow or unreliable?
- How long does an agent workflow take?
- How many tool calls failed in a run?
- Is the overall success rate improving?

AgentOps captures this telemetry in a local SQLite database and makes it queryable through MCP.

## Features

| MCP tool | Purpose |
|---|---|
| `start_run` | Create a tracked agent execution |
| `log_tool_call` | Record tool name, status, latency, and optional error |
| `finish_run` | Mark a run as successful or failed |
| `get_run_report` | Retrieve a run timeline and failure summary |
| `list_runs` | Browse recent runs with optional status filtering |
| `get_metrics` | Calculate aggregate reliability and latency metrics |

The server also exposes an `agentops://about` resource.

## Architecture

```text
MCP-compatible AI assistant / agent
              |
              | MCP over stdio
              v
       AgentOps MCP server
              |
     +--------+---------+
     |        |         |
  start_run  log_call  finish_run
     |        |         |
     +--------+---------+
              |
              v
       SQLite telemetry store
              |
       +------+------+
       |             |
   Run reports   Aggregate metrics
```

## Quick start

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/agentops-mcp.git
cd agentops-mcp
```

### 2. Create an environment and install

```bash
python -m venv .venv

# macOS/Linux
source .venv/bin/activate

# Windows PowerShell
# .venv\Scripts\Activate.ps1

pip install -e ".[dev]"
```

### 3. Configure persistence (optional)

By default, the database is created at `./agentops.sqlite3`.

```bash
# macOS/Linux
export AGENTOPS_DB_PATH="./agentops.sqlite3"

# Windows PowerShell
$env:AGENTOPS_DB_PATH = ".\agentops.sqlite3"
```

### 4. Start the MCP server

```bash
agentops-mcp
```

The server uses stdio transport, suitable for local MCP clients.

## Example MCP client configuration

Adapt this example to the configuration format supported by your MCP client:

```json
{
  "mcpServers": {
    "agentops": {
      "command": "python",
      "args": ["-m", "agentops_mcp.server"],
      "env": {
        "AGENTOPS_DB_PATH": "/absolute/path/to/agentops.sqlite3"
      }
    }
  }
}
```

## Example workflow

An assistant can use the tools in this order:

1. Call `start_run` with an agent name and task description.
2. Save the returned `run_id`.
3. Call `log_tool_call` after each tool invocation, recording its duration and outcome.
4. Call `finish_run` when the workflow completes.
5. Call `get_run_report` to inspect the run.
6. Call `get_metrics` to inspect aggregate performance.

Example interaction:

```text
User: Track a research agent run for me.

Assistant -> start_run(
  agent_name="ResearchAgent",
  task="Summarise public climate data"
)

Assistant -> log_tool_call(
  run_id="<returned-run-id>",
  tool_name="search_web",
  duration_ms=125.5,
  status="success"
)

Assistant -> log_tool_call(
  run_id="<returned-run-id>",
  tool_name="fetch_page",
  duration_ms=80,
  status="failed",
  error="HTTP 503"
)

Assistant -> finish_run(
  run_id="<returned-run-id>",
  status="failed",
  error="A required page could not be retrieved"
)

Assistant -> get_run_report(run_id="<returned-run-id>")
```

## Example aggregate metrics

`get_metrics` returns a JSON object shaped like this:

```json
{
  "total_runs": 12,
  "successful_runs": 9,
  "failed_runs": 3,
  "success_rate_percent": 75.0,
  "average_duration_ms": 1840.42,
  "tools": [
    {
      "tool_name": "search_web",
      "calls": 28,
      "failures": 2,
      "failure_rate_percent": 7.14,
      "average_duration_ms": 245.8
    }
  ]
}
```

Values above are illustrative, not live measurements.

## Run tests

```bash
pytest
```

## Data model

- **runs** stores the agent name, task description, lifecycle status, timestamps, duration, and optional error.
- **tool_calls** stores each tool invocation, its parent run, status, latency, timestamp, and optional error.

SQLite foreign keys ensure tool-call records belong to an existing run.

## Safety and limitations

- Telemetry is stored locally in SQLite.
- SQL is not exposed as an MCP tool.
- Inputs have length and status validation.
- Tool calls cannot be added after a run has completed.
- The server does not intercept or automatically instrument other agents; an agent or wrapper must explicitly report events using the MCP tools.
- Error messages and task descriptions may contain sensitive information. Redact credentials, tokens, personal data, and confidential content before logging.
- This is a local developer tool, not a hardened multi-tenant observability platform.

## Roadmap

- [ ] Automatic instrumentation wrappers for popular agent frameworks
- [ ] Token usage and model-cost tracking
- [ ] Trace parent/child spans for nested agents
- [ ] Retry and timeout analytics
- [ ] Configurable alert thresholds
- [ ] Dashboard for run timelines and reliability trends
- [ ] OpenTelemetry export

## Tech stack

Python · Model Context Protocol · SQLite

## Author

**Alaina Rahim**  
MSc Advanced Computer Science (Artificial Intelligence), University of Leeds
