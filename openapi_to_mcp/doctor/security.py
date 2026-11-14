"""Security-scheme diagnostics helpers for doctor."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

_SUPPORTED_SECURITY_TYPES = {"apiKey", "oauth2", "openIdConnect"}

if TYPE_CHECKING:
    from openapi_to_mcp.doctor.models import DoctorReport


def security_schemes(spec: dict[str, Any]) -> dict[str, Any]:
    """Return normalized OpenAPI security scheme definitions."""
    components = spec.get("components", {})
    if isinstance(components, dict):
        schemes = components.get("securitySchemes")
        if isinstance(schemes, dict):
            return schemes
    definitions = spec.get("securityDefinitions", {})
    return definitions if isinstance(definitions, dict) else {}


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


def check_security_header_conflicts(
    report: DoctorReport,
    *,
    source: object,
    schemes: dict[str, Any],
    location: str,
) -> None:
    """Warn when one security requirement targets the same header twice."""
    if not isinstance(source, list) or not isinstance(schemes, dict):
        return
    for requirement in source:
        if not isinstance(requirement, dict) or not _valid_scope_values(requirement):
            continue
        headers: dict[str, list[str]] = {}
        for scheme_name in requirement:
            if not isinstance(scheme_name, str):
                continue
            header = _runtime_auth_header(schemes.get(scheme_name))
            if header is None:
                continue
            headers.setdefault(header.lower(), []).append(scheme_name)
        conflicts = [names for names in headers.values() if len(names) > 1]
        if not conflicts:
            continue
        names = ", ".join(name for conflict in conflicts for name in conflict)
        report.add_warning(
            "conflicting_auth_headers",
            f"Security requirement combines schemes `{names}` that target the same HTTP header.",
            location,
            "Distinct auth values cannot share one header; use security alternatives or distinct header locations.",
        )


def _valid_scope_values(requirement: dict[object, object]) -> bool:
    """Return whether a security requirement has valid scope-array values."""
    return all(
        isinstance(scopes, list) and all(isinstance(scope, str) for scope in scopes)
        for scopes in requirement.values()
    )


def _runtime_auth_header(scheme: object) -> str | None:
    """Return the header targeted by a supported runtime auth scheme."""
    if not isinstance(scheme, dict):
        return None
    scheme_type = scheme.get("type")
    if scheme_type == "http":
        http_scheme = scheme.get("scheme")
        if isinstance(http_scheme, str) and http_scheme.lower() in {"basic", "bearer"}:
            return "Authorization"
    elif scheme_type in {"oauth2", "openIdConnect"}:
        return "Authorization"
    elif scheme_type == "apiKey":
        location = scheme.get("in")
        name = scheme.get("name")
        if (
            isinstance(location, str)
            and location.lower() == "header"
            and isinstance(name, str)
            and name.strip()
        ):
            return name
    return None


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
        if isinstance(http_scheme, str) and http_scheme.lower() in {"bearer", "basic"}:
            return
        report.add_error(
            "unsupported_http_auth",
            f"Security scheme `{name}` uses unsupported HTTP scheme `{http_scheme}`.",
            location,
            "Use HTTP basic/bearer, apiKey, oauth2, or openIdConnect for generated runtime auth.",
        )
        return
    report.add_error(
        "unsupported_security_scheme",
        f"Security scheme `{name}` uses unsupported type `{scheme_type}`.",
        location,
        "Use HTTP basic/bearer, apiKey, oauth2, or openIdConnect for generated runtime auth.",
    )
