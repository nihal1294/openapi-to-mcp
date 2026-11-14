"""OpenAPI compatibility checks for constructs the mapper cannot execute."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openapi_to_mcp.common.operations import OperationRef


@dataclass(frozen=True)
class OpenAPIFinding:
    """One OpenAPI construct that cannot be faithfully generated."""

    field: str
    location: str
    guidance: str


@dataclass(frozen=True)
class _ParameterRef:
    parameter: dict[str, Any]
    location: str


def openapi_operation_findings(
    spec: dict[str, Any], operation_ref: OperationRef
) -> list[OpenAPIFinding]:
    """Return unsupported OpenAPI constructs reachable from one operation."""
    findings: list[OpenAPIFinding] = []
    if operation_ref.origin == "additional":
        findings.append(
            OpenAPIFinding(
                "additionalOperations",
                operation_ref.location,
                "Additional operations are diagnostic-only. Use a supported fixed HTTP operation before generating an MCP server.",
            )
        )
    elif operation_ref.method == "QUERY":
        findings.append(
            OpenAPIFinding(
                "query",
                operation_ref.location,
                "QUERY operations are diagnostic-only. Use a supported fixed HTTP operation before generating an MCP server.",
            )
        )

    for parameter_ref in _effective_parameters(spec, operation_ref):
        if parameter_ref.parameter.get("in") != "querystring":
            continue
        findings.append(
            OpenAPIFinding(
                "in: querystring",
                f"{parameter_ref.location}.in",
                "Whole-query and content parameter serialization is not supported. Use individual `in: query` parameters instead.",
            )
        )
    return list(dict.fromkeys(findings))


def format_openapi_finding(finding: OpenAPIFinding) -> str:
    """Format a compatibility finding as an actionable mapping error."""
    return (
        f"unsupported OpenAPI construct `{finding.field}` at `{finding.location}`; "
        f"{finding.guidance}"
    )


def _effective_parameters(
    spec: dict[str, Any], operation_ref: OperationRef
) -> list[_ParameterRef]:
    path_location = f"paths.{operation_ref.path}.parameters"
    operation_location = f"{operation_ref.location}.parameters"
    path_parameters = _parameter_refs(
        spec, operation_ref.path_item.get("parameters"), path_location
    )
    operation_parameters = _parameter_refs(
        spec, operation_ref.operation.get("parameters"), operation_location
    )

    merged: list[_ParameterRef] = []
    index_by_key: dict[tuple[str, str], int] = {}
    for parameter_ref in [*path_parameters, *operation_parameters]:
        key = _parameter_key(parameter_ref.parameter)
        if key is None:
            merged.append(parameter_ref)
            continue
        previous = index_by_key.get(key)
        if previous is None:
            index_by_key[key] = len(merged)
            merged.append(parameter_ref)
        else:
            merged[previous] = parameter_ref
    return merged


def _parameter_refs(
    spec: dict[str, Any], candidates: object, base_location: str
) -> list[_ParameterRef]:
    if not isinstance(candidates, list):
        return []
    resolved: list[_ParameterRef] = []
    for index, candidate in enumerate(candidates):
        parameter = _resolve_parameter(spec, candidate, f"{base_location}[{index}]")
        if parameter is not None:
            resolved.append(parameter)
    return resolved


def _resolve_parameter(
    spec: dict[str, Any], candidate: object, location: str
) -> _ParameterRef | None:
    if not isinstance(candidate, dict):
        return None
    current = candidate
    current_location = location
    for _ in range(20):
        ref = current.get("$ref")
        if ref is None:
            return _ParameterRef(current, current_location)
        if not isinstance(ref, str) or not ref.startswith("#/"):
            return None
        resolved = _resolve_local_ref(spec, ref)
        if not isinstance(resolved, dict):
            return None
        current = resolved
        current_location = _location_for_ref(ref)
    return None


def _parameter_key(parameter: dict[str, Any]) -> tuple[str, str] | None:
    name = parameter.get("name")
    location = parameter.get("in")
    if not isinstance(name, str) or not isinstance(location, str):
        return None
    return (name, location)


def _resolve_local_ref(spec: dict[str, Any], ref: str) -> object:
    current: object = spec
    for token in ref[2:].split("/"):
        if not isinstance(current, dict):
            return None
        current = current.get(token.replace("~1", "/").replace("~0", "~"))
    return current


def _location_for_ref(ref: str) -> str:
    return ".".join(
        token.replace("~1", "/").replace("~0", "~") for token in ref[2:].split("/")
    )
