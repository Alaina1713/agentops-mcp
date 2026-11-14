"""Illustrative lifecycle using the same persistence layer as the MCP tools."""

from agentops_mcp import store
from agentops_mcp.server import (
    finish_run,
    get_metrics,
    get_run_report,
    log_tool_call,
    start_run,
)


def main():
    store.initialise()
    run = start_run("DemoResearchAgent", "Collect and summarise public transport data")
    run_id = run["run_id"]

    log_tool_call(run_id, "search_transport_api", 143.2, "success")
    log_tool_call(run_id, "normalise_records", 32.8, "success")
    log_tool_call(run_id, "generate_summary", 410.4, "failed", "Model request timed out")
    finish_run(run_id, "failed", "Summary generation failed")

    print("RUN REPORT")
    print(get_run_report(run_id))
    print("\\nAGGREGATE METRICS")
    print(get_metrics())


if __name__ == "__main__":
    main()
