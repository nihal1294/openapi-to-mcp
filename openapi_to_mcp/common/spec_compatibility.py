"""Compatibility checks shared by Swagger 2 diagnostics and mapping."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SwaggerFinding:
    """One Swagger 2 construct that cannot be represented by the mapper."""

    field: str
    location: str


def swagger_operation_findings(
    spec: dict[str, Any],
    method: str,
    path: str,
    path_item: dict[str, Any],
    operation: dict[str, Any],
) -> list[SwaggerFinding]:
    """Return unsupported Swagger 2 constructs used by one operation."""
    if spec.get("swagger") != "2.0":
        return []
    base = f"paths.{path}"
    findings = _parameter_findings(
        spec, path_item.get("parameters"), f"{base}.parameters"
    )
    findings.extend(
        _parameter_findings(
            spec, operation.get("parameters"), f"{base}.{method.lower()}.parameters"
        )
    )
    findings.extend(_security_findings(spec, operation, base, method))
    return list(dict.fromkeys(findings))


def format_swagger_finding(finding: SwaggerFinding) -> str:
    """Format one compatibility finding as an actionable mapping error."""
    return (
        f"unsupported Swagger 2 construct `{finding.field}` at `{finding.location}`; "
        "convert this operation to OpenAPI 3 before generation."
    )


def _parameter_findings(
    spec: dict[str, Any], parameters: object, location: str
) -> list[SwaggerFinding]:
    if not isinstance(parameters, list):
        return []
    findings: list[SwaggerFinding] = []
    for index, candidate in enumerate(parameters):
        parameter = _resolve_parameter(spec, candidate)
        field_location = f"{location}[{index}]"
        if not isinstance(parameter, dict):
            if isinstance(candidate, dict) and "$ref" in candidate:
                findings.append(SwaggerFinding("$ref", f"{field_location}.$ref"))
            continue
        parameter_in = parameter.get("in")
        if parameter_in in {"body", "formData"}:
            findings.append(
                SwaggerFinding(f"in: {parameter_in}", f"{field_location}.in")
            )
        if (
            parameter_in in {"path", "query", "header", "cookie"}
            and "type" in parameter
        ):
            findings.append(SwaggerFinding("type", f"{field_location}.type"))
    return findings


def _resolve_parameter(
    spec: dict[str, Any], candidate: object
) -> dict[str, Any] | None:
    if not isinstance(candidate, dict):
        return None
    current = candidate
    for _ in range(20):
        ref = current.get("$ref")
        if ref is None:
            return current
        if not isinstance(ref, str):
            return None
        resolved = _resolve_local_ref(spec, ref)
        if not isinstance(resolved, dict):
            return None
        current = resolved
    return None


def _resolve_local_ref(spec: dict[str, Any], ref: str) -> object:
    if not ref.startswith("#/"):
        return None
    current: object = spec
    for token in ref[2:].split("/"):
        if not isinstance(current, dict):
            return None
        current = current.get(token.replace("~1", "/").replace("~0", "~"))
    return current


def _security_findings(
    spec: dict[str, Any], operation: dict[str, Any], base: str, method: str
) -> list[SwaggerFinding]:
    location = (
        f"{base}.{method.lower()}.security" if "security" in operation else "security"
    )
    requirements = (
        operation.get("security") if "security" in operation else spec.get("security")
    )
    if not isinstance(requirements, list) or not requirements:
        return []
    definitions = spec.get("securityDefinitions")
    names = {
        name
        for item in requirements
        if isinstance(item, dict)
        for name in item
        if isinstance(name, str)
    }
    if not names:
        return []
    field = (
        "securityDefinitions"
        if isinstance(definitions, dict) and names & definitions.keys()
        else "security"
    )
    return [SwaggerFinding(field, location)]
