"""Runtime override options for the `run` command."""

from __future__ import annotations

from typing import TYPE_CHECKING

import rich_click as click

from openapi_to_mcp.common.performance_presets import PERFORMANCE_PRESET_NAMES

if TYPE_CHECKING:
    from collections.abc import Mapping

RUNTIME_ENV_MAP = {
    "performance_preset": "MCP_PERFORMANCE_PRESET",
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
    "retry_max_retries": "MCP_RETRY_MAX_RETRIES",
    "retry_budget_per_minute": "MCP_RETRY_BUDGET_PER_MINUTE",
    "circuit_breaker_failure_threshold": "MCP_CIRCUIT_BREAKER_FAILURE_THRESHOLD",
    "circuit_breaker_cooldown_ms": "MCP_CIRCUIT_BREAKER_COOLDOWN_MS",
    "tool_access_mode": "MCP_TOOL_ACCESS_MODE",
    "tool_access_default": "MCP_TOOL_ACCESS_DEFAULT",
    "tool_identity_header": "MCP_TOOL_IDENTITY_HEADER",
    "tool_allowlists": "MCP_TOOL_ALLOWLISTS",
    "audit_mode": "MCP_AUDIT_MODE",
    "audit_redact_headers": "MCP_AUDIT_REDACT_HEADERS",
    "audit_redact_query_params": "MCP_AUDIT_REDACT_QUERY_PARAMS",
    "audit_redact_cookie_names": "MCP_AUDIT_REDACT_COOKIE_NAMES",
    "audit_redact_request_body_paths": "MCP_AUDIT_REDACT_REQUEST_BODY_PATHS",
    "audit_redact_response_body_paths": "MCP_AUDIT_REDACT_RESPONSE_BODY_PATHS",
}

run_runtime_override_options = [
    click.option(
        "--performance-preset",
        type=click.Choice(PERFORMANCE_PRESET_NAMES, case_sensitive=False),
        help="Apply a named bundle of runtime defaults. Explicit runtime overrides still win.",
    ),
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
    click.option(
        "--retry-max-retries",
        type=int,
        help="Maximum retry count for safe tools. Retries only activate when retry budget is also > 0. Use 0 to disable retries.",
    ),
    click.option(
        "--retry-budget-per-minute",
        type=int,
        help="Maximum retry attempts per tool per minute for safe tools. Retries only activate when retry count is also > 0. Use 0 to disable retries.",
    ),
    click.option(
        "--circuit-breaker-failure-threshold",
        type=int,
        help="Consecutive breaker-qualifying failures before safe tools open the circuit. Use 0 to disable.",
    ),
    click.option(
        "--circuit-breaker-cooldown-ms",
        type=int,
        help="Cooldown window before a safe tool circuit allows one half-open probe. Only applies when failure threshold is > 0.",
    ),
    click.option(
        "--tool-access-mode",
        type=click.Choice(["off", "allowlist"], case_sensitive=False),
        help="Request-scoped tool access mode for generated runtimes.",
    ),
    click.option(
        "--tool-access-default",
        type=click.Choice(["allow", "deny"], case_sensitive=False),
        help="Default tool-access behavior when no caller-specific allowlist matches.",
    ),
    click.option(
        "--tool-identity-header",
        help="Header name used to derive caller identity for streamable-http access control.",
    ),
    click.option(
        "--tool-allowlists",
        help="JSON object mapping caller identities to arrays of allowed tool names.",
    ),
    click.option(
        "--audit-mode",
        type=click.Choice(["off", "logs"], case_sensitive=False),
        help="Audit sink mode for generated runtimes.",
    ),
    click.option(
        "--audit-redact-headers",
        help="Comma-separated header names redacted in audit events.",
    ),
    click.option(
        "--audit-redact-query-params",
        help="Comma-separated query parameter names redacted in audit events.",
    ),
    click.option(
        "--audit-redact-cookie-names",
        help="Comma-separated cookie names redacted in audit events.",
    ),
    click.option(
        "--audit-redact-request-body-paths",
        help="Comma-separated dot paths redacted in request-body audit fields.",
    ),
    click.option(
        "--audit-redact-response-body-paths",
        help="Comma-separated dot paths redacted in response-body audit fields.",
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
