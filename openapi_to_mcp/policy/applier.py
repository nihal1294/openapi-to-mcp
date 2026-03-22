"""Apply `mcpgen.yaml` policy rules to mapped tools."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

from openapi_to_mcp.common.exceptions import PolicyConfigError

if TYPE_CHECKING:
    from openapi_to_mcp.policy.models import (
        ExecutionOverride,
        PolicyConfig,
        SelectorSet,
    )


def apply_policy(
    mcp_tools: list[dict[str, Any]], policy: PolicyConfig | None
) -> list[dict[str, Any]]:
    """Return policy-adjusted mapped tools."""
    if policy is None:
        return mcp_tools
    filtered = [deepcopy(tool) for tool in mcp_tools if _should_keep_tool(tool, policy)]
    updated = [_apply_tool_overrides(tool, policy) for tool in filtered]
    _ensure_unique_names(updated)
    return updated


def _should_keep_tool(tool: dict[str, Any], policy: PolicyConfig) -> bool:
    operation = _tool_operation_key(tool)
    original_name = _tool_name(tool)
    if not policy.include.is_empty and not _matches_selectors(
        original_name, operation, policy.include
    ):
        return False
    return not _matches_selectors(original_name, operation, policy.exclude)


def _matches_selectors(
    original_name: str, operation: str, selectors: SelectorSet
) -> bool:
    return operation in selectors.operations or original_name in selectors.names


def _apply_tool_overrides(tool: dict[str, Any], policy: PolicyConfig) -> dict[str, Any]:
    operation = _tool_operation_key(tool)
    original_name = _tool_name(tool)
    renamed_name = _resolve_rename(operation, original_name, policy)
    tool["name"] = renamed_name
    _apply_auth_override(tool, operation, original_name, renamed_name, policy)
    _apply_execution_override(tool, operation, original_name, renamed_name, policy)
    return tool


def _resolve_rename(operation: str, original_name: str, policy: PolicyConfig) -> str:
    operation_rename = policy.rename_operations.get(operation)
    if operation_rename is not None:
        return operation_rename
    name_rename = policy.rename_names.get(original_name)
    if name_rename is not None:
        return name_rename
    return original_name


def _apply_auth_override(
    tool: dict[str, Any],
    operation: str,
    original_name: str,
    renamed_name: str,
    policy: PolicyConfig,
) -> None:
    override = _lookup_override(
        operation,
        original_name,
        renamed_name,
        policy.auth_operations,
        policy.auth_names,
    )
    if override is None:
        return
    if override.security is not None:
        tool["_original_security"] = override.security
    if override.security_schemes is not None:
        tool["_original_security_schemes"] = override.security_schemes


def _apply_execution_override(
    tool: dict[str, Any],
    operation: str,
    original_name: str,
    renamed_name: str,
    policy: PolicyConfig,
) -> None:
    override = _lookup_override(
        operation,
        original_name,
        renamed_name,
        policy.execution_operations,
        policy.execution_names,
    )
    if override is None:
        return
    _validate_safe_method_execution_override(tool, override)
    metadata = _build_execution_metadata(override)
    if metadata:
        tool["_policy_execution"] = metadata


def _validate_safe_method_execution_override(
    tool: dict[str, Any],
    override: ExecutionOverride,
) -> None:
    if not _has_safe_method_execution_override(override):
        return
    method = _tool_method(tool)
    if method in {"GET", "HEAD", "OPTIONS"}:
        return
    raise PolicyConfigError(
        "cache_ttl_ms, rate_limit_per_minute, retry_max_retries, "
        "retry_budget_per_minute, circuit_breaker_failure_threshold, and "
        "circuit_breaker_cooldown_ms require a safe HTTP method "
        "(GET, HEAD, or OPTIONS)."
    )


def _has_safe_method_execution_override(override: ExecutionOverride) -> bool:
    return any(
        value is not None
        for value in (
            override.cache_ttl_ms,
            override.rate_limit_per_minute,
            override.retry_max_retries,
            override.retry_budget_per_minute,
            override.circuit_breaker_failure_threshold,
            override.circuit_breaker_cooldown_ms,
        )
    )


def _build_execution_metadata(override: ExecutionOverride) -> dict[str, int]:
    metadata_pairs = (
        ("maxConcurrency", override.max_concurrency),
        ("timeoutMs", override.timeout_ms),
        ("cacheTtlMs", override.cache_ttl_ms),
        ("rateLimitPerMinute", override.rate_limit_per_minute),
        ("retryMaxRetries", override.retry_max_retries),
        ("retryBudgetPerMinute", override.retry_budget_per_minute),
        (
            "circuitBreakerFailureThreshold",
            override.circuit_breaker_failure_threshold,
        ),
        ("circuitBreakerCooldownMs", override.circuit_breaker_cooldown_ms),
    )
    return {
        runtime_key: value for runtime_key, value in metadata_pairs if value is not None
    }


def _lookup_override[T](
    operation: str,
    original_name: str,
    renamed_name: str,
    operation_overrides: dict[str, T],
    name_overrides: dict[str, T],
) -> T | None:
    operation_override = operation_overrides.get(operation)
    if operation_override is not None:
        return operation_override
    original_override = name_overrides.get(original_name)
    if original_override is not None:
        return original_override
    if renamed_name == original_name:
        return None
    return name_overrides.get(renamed_name)


def _ensure_unique_names(mcp_tools: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for tool in mcp_tools:
        tool_name = _tool_name(tool)
        if tool_name in seen:
            raise PolicyConfigError(
                f"Policy produced duplicate tool name `{tool_name}`."
            )
        seen.add(tool_name)


def _tool_name(tool: dict[str, Any]) -> str:
    name = tool.get("name")
    if isinstance(name, str) and name:
        return name
    raise PolicyConfigError(f"Mapped tool is missing a valid name: {tool!r}")


def _tool_operation_key(tool: dict[str, Any]) -> str:
    method = tool.get("_original_method")
    path = tool.get("_original_path")
    if isinstance(method, str) and method and isinstance(path, str) and path:
        return f"{method.upper()} {path}"
    raise PolicyConfigError(f"Mapped tool is missing operation metadata: {tool!r}")


def _tool_method(tool: dict[str, Any]) -> str:
    method = tool.get("_original_method")
    if isinstance(method, str) and method:
        return method.upper()
    raise PolicyConfigError(f"Mapped tool is missing HTTP method metadata: {tool!r}")
