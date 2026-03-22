"""Parse typed policy models from `mcpgen.yaml` payloads."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openapi_to_mcp.policy.models import (
    AuthOverride,
    ExecutionOverride,
    GenerationDefaults,
    PolicyConfig,
    SelectorSet,
)
from openapi_to_mcp.policy.validators import (
    mapping_value,
    optional_bool,
    optional_choice,
    optional_int,
    optional_scheme_mapping,
    optional_security_list,
    optional_string,
    parse_string_mapping,
    string_list,
)

if TYPE_CHECKING:
    from pathlib import Path

from openapi_to_mcp.mapping.tool_grouping import TOOL_GROUPING_MODES

_ALLOWED_TRANSPORTS = {"stdio", "streamable-http"}
_ALLOWED_ERROR_MODES = {"fail", "skip"}
_ALLOWED_RUNTIME_VALIDATION = {"none", "input"}


def parse_policy_config(payload: dict[str, Any], source_path: Path) -> PolicyConfig:
    """Build a typed policy config from a validated payload."""
    tools = mapping_value(payload.get("tools"), "tools")
    renames = mapping_value(tools.get("rename"), "tools.rename")
    auth = mapping_value(payload.get("auth"), "auth")
    execution = mapping_value(payload.get("execution"), "execution")
    return PolicyConfig(
        source_path=source_path,
        generation=_parse_generation_defaults(payload.get("generate")),
        include=_parse_selectors(tools.get("include"), "tools.include"),
        exclude=_parse_selectors(tools.get("exclude"), "tools.exclude"),
        rename_operations=parse_string_mapping(
            renames.get("operations"),
            "tools.rename.operations",
        ),
        rename_names=parse_string_mapping(renames.get("names"), "tools.rename.names"),
        auth_operations=_parse_auth_mapping(auth.get("operations"), "auth.operations"),
        auth_names=_parse_auth_mapping(auth.get("names"), "auth.names"),
        execution_operations=_parse_execution_mapping(
            execution.get("operations"),
            "execution.operations",
        ),
        execution_names=_parse_execution_mapping(
            execution.get("names"),
            "execution.names",
        ),
    )


def _parse_generation_defaults(value: object) -> GenerationDefaults:
    config = mapping_value(value, "generate")
    return GenerationDefaults(
        mcp_server_name=optional_string(
            config.get("mcp_server_name"), "generate.mcp_server_name"
        ),
        mcp_server_version=optional_string(
            config.get("mcp_server_version"), "generate.mcp_server_version"
        ),
        tool_grouping=optional_choice(
            config.get("tool_grouping"),
            "generate.tool_grouping",
            TOOL_GROUPING_MODES,
        ),
        transport=optional_choice(
            config.get("transport"),
            "generate.transport",
            _ALLOWED_TRANSPORTS,
        ),
        host=optional_string(config.get("host"), "generate.host"),
        port=optional_int(config.get("port"), "generate.port", minimum=1),
        mcp_endpoint=optional_string(
            config.get("mcp_endpoint"), "generate.mcp_endpoint"
        ),
        strict=optional_bool(config.get("strict"), "generate.strict"),
        runtime_validation=optional_choice(
            config.get("runtime_validation"),
            "generate.runtime_validation",
            _ALLOWED_RUNTIME_VALIDATION,
        ),
        on_mapping_error=optional_choice(
            config.get("on_mapping_error"),
            "generate.on_mapping_error",
            _ALLOWED_ERROR_MODES,
        ),
        on_schema_error=optional_choice(
            config.get("on_schema_error"),
            "generate.on_schema_error",
            _ALLOWED_ERROR_MODES,
        ),
    )


def _parse_selectors(value: object, field_name: str) -> SelectorSet:
    config = mapping_value(value, field_name)
    return SelectorSet(
        operations=frozenset(
            string_list(config.get("operations"), f"{field_name}.operations")
        ),
        names=frozenset(string_list(config.get("names"), f"{field_name}.names")),
    )


def _parse_auth_mapping(value: object, field_name: str) -> dict[str, AuthOverride]:
    config = mapping_value(value, field_name)
    return {
        key: _parse_auth_override(item, f"{field_name}.{key}")
        for key, item in config.items()
    }


def _parse_auth_override(value: object, field_name: str) -> AuthOverride:
    entry = mapping_value(value, field_name)
    return AuthOverride(
        security=optional_security_list(
            entry.get("security"), f"{field_name}.security"
        ),
        security_schemes=optional_scheme_mapping(
            entry.get("security_schemes"),
            f"{field_name}.security_schemes",
        ),
    )


def _parse_execution_mapping(
    value: object, field_name: str
) -> dict[str, ExecutionOverride]:
    config = mapping_value(value, field_name)
    return {
        key: _parse_execution_override(item, f"{field_name}.{key}")
        for key, item in config.items()
    }


def _parse_execution_override(value: object, field_name: str) -> ExecutionOverride:
    entry = mapping_value(value, field_name)
    return ExecutionOverride(
        max_concurrency=optional_int(
            entry.get("max_concurrency"),
            f"{field_name}.max_concurrency",
            minimum=1,
        ),
        timeout_ms=optional_int(
            entry.get("timeout_ms"),
            f"{field_name}.timeout_ms",
            minimum=1,
        ),
        cache_ttl_ms=optional_int(
            entry.get("cache_ttl_ms"),
            f"{field_name}.cache_ttl_ms",
            minimum=0,
        ),
        rate_limit_per_minute=optional_int(
            entry.get("rate_limit_per_minute"),
            f"{field_name}.rate_limit_per_minute",
            minimum=0,
        ),
        retry_max_retries=optional_int(
            entry.get("retry_max_retries"),
            f"{field_name}.retry_max_retries",
            minimum=0,
        ),
        retry_budget_per_minute=optional_int(
            entry.get("retry_budget_per_minute"),
            f"{field_name}.retry_budget_per_minute",
            minimum=0,
        ),
        circuit_breaker_failure_threshold=optional_int(
            entry.get("circuit_breaker_failure_threshold"),
            f"{field_name}.circuit_breaker_failure_threshold",
            minimum=0,
        ),
        circuit_breaker_cooldown_ms=optional_int(
            entry.get("circuit_breaker_cooldown_ms"),
            f"{field_name}.circuit_breaker_cooldown_ms",
            minimum=1,
        ),
    )
