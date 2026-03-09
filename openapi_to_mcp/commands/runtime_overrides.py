"""Runtime override options for the `run` command."""

from __future__ import annotations

from typing import TYPE_CHECKING

import rich_click as click

if TYPE_CHECKING:
    from collections.abc import Mapping

RUNTIME_ENV_MAP = {
    "origin_allowlist": "MCP_ALLOWED_ORIGINS",
    "host_allowlist": "MCP_ALLOWED_HOSTS",
    "max_concurrency": "MCP_MAX_CONCURRENCY",
    "per_tool_max_concurrency": "MCP_PER_TOOL_MAX_CONCURRENCY",
    "max_queue_size": "MCP_MAX_QUEUE_SIZE",
    "queue_timeout_ms": "MCP_QUEUE_TIMEOUT_MS",
    "tool_timeout_ms": "MCP_TOOL_TIMEOUT_MS",
}

run_runtime_override_options = [
    click.option(
        "--origin-allowlist",
        help="Comma-separated origins allowed for streamable-http.",
    ),
    click.option(
        "--host-allowlist",
        help="Comma-separated Host header values allowed for streamable-http.",
    ),
    click.option(
        "--max-concurrency", type=int, help="Maximum concurrent tool executions."
    ),
    click.option(
        "--per-tool-max-concurrency",
        type=int,
        help="Maximum concurrent executions per tool.",
    ),
    click.option("--max-queue-size", type=int, help="Maximum queued executions."),
    click.option(
        "--queue-timeout-ms", type=int, help="Maximum queue wait time in milliseconds."
    ),
    click.option(
        "--tool-timeout-ms",
        type=int,
        help="Maximum tool execution time in milliseconds.",
    ),
]


def build_runtime_override_env(
    values: Mapping[str, str | int | None],
) -> dict[str, str]:
    """Map `run` command override values to generated runtime env vars."""
    overrides: dict[str, str] = {}
    for option_name, env_name in RUNTIME_ENV_MAP.items():
        value = values.get(option_name)
        if value is None:
            continue
        overrides[env_name] = str(value)
    return overrides
