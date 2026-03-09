"""Security-scheme diagnostics helpers for doctor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

_SUPPORTED_SECURITY_TYPES = {"apiKey", "oauth2", "openIdConnect"}

if TYPE_CHECKING:
    from openapi_to_mcp.doctor.models import DoctorReport


def security_schemes(spec: dict[str, Any]) -> dict[str, Any]:
    """Return normalized OpenAPI security scheme definitions."""
    components = spec.get("components", {})
    if not isinstance(components, dict):
        return {}
    schemes = components.get("securitySchemes", {})
    return schemes if isinstance(schemes, dict) else {}


def referenced_scheme_names(source: object) -> list[str]:
    """Extract security scheme names from a requirement list."""
    if not isinstance(source, list):
        return []
    names: list[str] = []
    for requirement in source:
        if not isinstance(requirement, dict):
            continue
        names.extend(name for name in requirement if isinstance(name, str))
    return names


def check_security_scheme(
    report: DoctorReport,
    *,
    name: str,
    scheme: dict[str, Any] | None,
    location: str,
) -> None:
    """Record a doctor issue for undefined or unsupported security schemes."""
    if not isinstance(scheme, dict):
        report.add_error(
            "undefined_security_scheme",
            f"Security requirement references undefined scheme `{name}`.",
            location,
            "Define the scheme under `components.securitySchemes`.",
        )
        return
    scheme_type = scheme.get("type")
    if scheme_type in _SUPPORTED_SECURITY_TYPES:
        return
    if scheme_type == "http":
        http_scheme = scheme.get("scheme")
        if isinstance(http_scheme, str) and http_scheme.lower() == "bearer":
            return
        report.add_error(
            "unsupported_http_auth",
            f"Security scheme `{name}` uses unsupported HTTP scheme `{http_scheme}`.",
            location,
            "Use bearer, apiKey, oauth2, or openIdConnect for generated runtime auth.",
        )
        return
    report.add_error(
        "unsupported_security_scheme",
        f"Security scheme `{name}` uses unsupported type `{scheme_type}`.",
        location,
        "Use bearer, apiKey, oauth2, or openIdConnect for generated runtime auth.",
    )
