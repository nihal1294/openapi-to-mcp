"""Apply `mcpgen.yaml` policy rules to mapped tools."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

from openapi_to_mcp.common.exceptions import PolicyConfigError

if TYPE_CHECKING:
    from openapi_to_mcp.policy.models import PolicyConfig, SelectorSet


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
    return (
        policy.rename_operations.get(operation)
        or policy.rename_names.get(original_name)
        or original_name
    )


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
    metadata: dict[str, int] = {}
    if override.max_concurrency is not None:
        metadata["maxConcurrency"] = override.max_concurrency
    if override.timeout_ms is not None:
        metadata["timeoutMs"] = override.timeout_ms
    if metadata:
        tool["_policy_execution"] = metadata


def _lookup_override[T](
    operation: str,
    original_name: str,
    renamed_name: str,
    operation_overrides: dict[str, T],
    name_overrides: dict[str, T],
) -> T | None:
    return (
        operation_overrides.get(operation)
        or name_overrides.get(original_name)
        or name_overrides.get(renamed_name)
    )


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
