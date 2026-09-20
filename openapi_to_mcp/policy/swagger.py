"""Evaluate Swagger compatibility against policy-adjusted tool metadata."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openapi_to_mcp.policy.applier import apply_policy

if TYPE_CHECKING:
    from openapi_to_mcp.common.spec_compatibility import SwaggerFinding
    from openapi_to_mcp.policy.models import PolicyConfig


def effective_swagger_findings(
    findings: list[SwaggerFinding],
    tool: dict[str, Any],
    policy: PolicyConfig | None,
) -> list[SwaggerFinding]:
    """Keep findings that remain relevant after tool selection and auth overrides."""
    if not findings or policy is None:
        return findings
    selected = apply_policy([tool], policy)
    if not selected:
        return []
    if _has_security_metadata(selected[0]):
        return [
            finding
            for finding in findings
            if finding.field not in {"security", "securityDefinitions"}
        ]
    return findings


def _has_security_metadata(tool: dict[str, Any]) -> bool:
    requirements = tool.get("_original_security")
    if requirements is None or requirements == []:
        return True
    schemes = tool.get("_original_security_schemes")
    if not isinstance(requirements, list) or not isinstance(schemes, dict):
        return False
    return all(
        isinstance(requirement, dict)
        and all(isinstance(schemes.get(name), dict) for name in requirement)
        for requirement in requirements
    )
