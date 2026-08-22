"""Typed command options and immutable generation request values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypedDict, cast

if TYPE_CHECKING:
    from collections.abc import Mapping

    from openapi_to_mcp.common.error_policy import ErrorMode
    from openapi_to_mcp.policy.models import PolicyConfig


class _GenerationClickOptions(TypedDict):
    openapi_json: str
    config: str | None
    mcp_server_name: str | None
    mcp_server_version: str | None
    tool_grouping: str
    transport: str
    host: str
    port: int | None
    mcp_endpoint: str
    strict: bool
    runtime_validation: str
    on_mapping_error: str | None
    on_schema_error: str | None


class GenerateClickOptions(_GenerationClickOptions):
    """Typed options supplied by Click to the generate command."""

    output_dir: str


class RunClickOptions(_GenerationClickOptions):
    """Typed options supplied by Click to the run command."""

    output_dir: str | None
    target_api_base_url: str | None
    env_source: str | None
    performance_preset: str | None
    origin_allowlist: str | None
    host_allowlist: str | None
    max_concurrency: int | None
    per_tool_max_concurrency: int | None
    max_queue_size: int | None
    queue_timeout_ms: int | None
    tool_timeout_ms: int | None
    cache_ttl_ms: int | None
    cache_max_entries: int | None
    rate_limit_per_minute: int | None
    retry_max_retries: int | None
    retry_budget_per_minute: int | None
    circuit_breaker_failure_threshold: int | None
    circuit_breaker_cooldown_ms: int | None
    tool_access_mode: str | None
    tool_access_default: str | None
    tool_identity_header: str | None
    tool_allowlists: str | None
    audit_mode: str | None
    audit_redact_headers: str | None
    audit_redact_query_params: str | None
    audit_redact_cookie_names: str | None
    audit_redact_request_body_paths: str | None
    audit_redact_response_body_paths: str | None


@dataclass(frozen=True, slots=True)
class ServerIdentity:
    """Optional identity overrides for the generated MCP server."""

    name: str | None
    version: str | None


@dataclass(frozen=True, slots=True)
class TransportSettings:
    """Transport configuration for the generated MCP server."""

    kind: str
    host: str
    port: int | None
    endpoint: str


@dataclass(frozen=True, slots=True)
class GenerationBehavior:
    """Mapping, grouping, and validation behavior for generation."""

    tool_grouping: str
    strict: bool
    runtime_validation: str
    on_mapping_error: ErrorMode | None
    on_schema_error: ErrorMode | None


@dataclass(frozen=True, slots=True)
class GenerationSettings:
    """Composed settings used by the generation service."""

    identity: ServerIdentity
    transport: TransportSettings
    behavior: GenerationBehavior


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """Describe one complete MCP project generation operation."""

    source: str
    output_dir: str
    settings: GenerationSettings
    policy_config: PolicyConfig | None = None


GENERATION_SETTING_NAMES = (
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


def generation_cli_values(options: Mapping[str, Any]) -> dict[str, Any]:
    """Select generation settings from a Click option mapping."""
    return {name: options[name] for name in GENERATION_SETTING_NAMES}


def compose_generation_request(
    source: str,
    output_dir: str,
    values: Mapping[str, Any],
    policy_config: PolicyConfig | None,
) -> GenerationRequest:
    """Compose an immutable generation request from resolved option values."""
    identity = ServerIdentity(
        name=cast("str | None", values["mcp_server_name"]),
        version=cast("str | None", values["mcp_server_version"]),
    )
    transport = TransportSettings(
        kind=cast("str", values["transport"]),
        host=cast("str", values["host"]),
        port=cast("int | None", values["port"]),
        endpoint=cast("str", values["mcp_endpoint"]),
    )
    behavior = GenerationBehavior(
        tool_grouping=cast("str", values["tool_grouping"]),
        strict=cast("bool", values["strict"]),
        runtime_validation=cast("str", values["runtime_validation"]),
        on_mapping_error=cast("ErrorMode | None", values["on_mapping_error"]),
        on_schema_error=cast("ErrorMode | None", values["on_schema_error"]),
    )
    settings = GenerationSettings(identity, transport, behavior)
    return GenerationRequest(source, output_dir, settings, policy_config)
