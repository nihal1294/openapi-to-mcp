"""Resolve command options against policy-file defaults."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from click.core import Context, ParameterSource

if TYPE_CHECKING:
    from openapi_to_mcp.policy.models import PolicyConfig

_GENERATION_DEFAULT_FIELDS = (
    "mcp_server_name",
    "mcp_server_version",
    "tool_grouping",
    "transport",
    "host",
    "port",
    "mcp_endpoint",
    "strict",
    "runtime_validation",
    "on_mapping_error",
    "on_schema_error",
)


def resolve_generation_settings(
    ctx: Context,
    policy: PolicyConfig | None,
    cli_values: dict[str, Any],
) -> dict[str, Any]:
    """Return generation settings after applying policy defaults."""
    if policy is None:
        return cli_values
    resolved = dict(cli_values)
    for field_name in _GENERATION_DEFAULT_FIELDS:
        config_value = getattr(policy.generation, field_name)
        if config_value is None:
            continue
        if ctx.get_parameter_source(field_name) == ParameterSource.DEFAULT:
            resolved[field_name] = config_value
    return resolved
