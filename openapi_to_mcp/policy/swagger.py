"""Evaluate Swagger compatibility against policy-adjusted tool metadata."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openapi_to_mcp.policy.applier import apply_policy, preview_auth_policy

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
    return _filter_security_findings(findings, selected[0])


def preview_swagger_findings(
    findings: list[SwaggerFinding], tool: dict[str, Any], policy: PolicyConfig | None
) -> list[SwaggerFinding]:
    """Evaluate selection and auth without unrelated execution policy effects."""
    if not findings or policy is None:
        return findings
    selected = preview_auth_policy(tool, policy)
    if selected is None:
        return []
    return _filter_security_findings(findings, selected)


def _filter_security_findings(
    findings: list[SwaggerFinding], tool: dict[str, Any]
) -> list[SwaggerFinding]:
    if _has_supported_security_metadata(tool):
        return [
            finding
            for finding in findings
            if finding.field not in {"security", "securityDefinitions"}
        ]
    return findings


def _has_supported_security_metadata(tool: dict[str, Any]) -> bool:
    requirements = tool.get("_original_security")
    if requirements is None or requirements == []:
        return True
    schemes = tool.get("_original_security_schemes")
    if not isinstance(requirements, list) or not isinstance(schemes, dict):
        return False
    return all(
        isinstance(requirement, dict)
        and all(_runtime_supports_scheme(schemes.get(name)) for name in requirement)
        for requirement in requirements
    )


def _runtime_supports_scheme(scheme: object) -> bool:
    """Match the scheme types handled by the generated auth resolver."""
    if not isinstance(scheme, dict):
        return False
    scheme_type = str(scheme.get("type", "")).lower()
    if scheme_type == "http":
        return str(scheme.get("scheme", "")).lower() in {"bearer", "basic"}
    if scheme_type == "apikey":
        location = scheme.get("in")
        name = scheme.get("name")
        return (
            isinstance(location, str)
            and location.lower() in {"header", "query", "cookie"}
            and isinstance(name, str)
            and bool(name.strip())
        )
    return scheme_type in {"oauth2", "openidconnect"}
