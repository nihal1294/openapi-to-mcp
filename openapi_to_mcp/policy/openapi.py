"""Policy selection for OpenAPI compatibility findings."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openapi_to_mcp.mapping.utils import generate_tool_name
from openapi_to_mcp.policy.applier import apply_policy

if TYPE_CHECKING:
    from openapi_to_mcp.common.operations import OperationRef
    from openapi_to_mcp.policy.models import PolicyConfig


def is_openapi_operation_selected(
    operation_ref: OperationRef, policy: PolicyConfig | None
) -> bool:
    """Return whether policy would retain an operation with this original identity."""
    if policy is None:
        return True
    candidate_name = operation_ref.operation.get("operationId") or generate_tool_name(
        operation_ref.method, operation_ref.path
    )
    if not isinstance(candidate_name, str):
        return True
    provisional_tool: dict[str, Any] = {
        "name": candidate_name,
        "_original_method": operation_ref.method,
        "_original_path": operation_ref.path,
    }
    return bool(apply_policy([provisional_tool], policy))
