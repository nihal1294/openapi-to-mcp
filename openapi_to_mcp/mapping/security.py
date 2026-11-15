"""Shared extraction of operation security metadata."""

from typing import Any


def operation_security(
    spec: dict[str, Any], operation: dict[str, Any]
) -> list[dict[str, Any]] | None:
    """Return normalized operation or document security requirements."""
    value = (
        operation.get("security") if "security" in operation else spec.get("security")
    )
    if not isinstance(value, list):
        return None
    return [item for item in value if isinstance(item, dict)]


def operation_security_schemes(
    spec: dict[str, Any], requirements: list[dict[str, Any]] | None
) -> dict[str, dict[str, Any]]:
    """Return component definitions referenced by the requirements."""
    if not requirements:
        return {}
    components = spec.get("components", {})
    if not isinstance(components, dict):
        return {}
    schemes = components.get("securitySchemes", {})
    if not isinstance(schemes, dict):
        return {}
    names = {
        name
        for requirement in requirements
        for name in requirement
        if isinstance(name, str)
    }
    return {
        name: schemes[name] for name in names if isinstance(schemes.get(name), dict)
    }
