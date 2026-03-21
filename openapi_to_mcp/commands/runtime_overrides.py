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
    "cache_ttl_ms": "MCP_CACHE_TTL_MS",
    "cache_max_entries": "MCP_CACHE_MAX_ENTRIES",
    "rate_limit_per_minute": "MCP_RATE_LIMIT_PER_MINUTE",
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
    click.option(
        "--cache-ttl-ms",
        type=int,
        help="Default cache TTL in milliseconds for safe tools. Use 0 to disable.",
    ),
    click.option(
        "--cache-max-entries",
        type=int,
        help="Maximum in-memory cache entries retained when caching is enabled.",
    ),
    click.option(
        "--rate-limit-per-minute",
        type=int,
        help="Default per-tool rate limit for safe tools. Use 0 to disable.",
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
