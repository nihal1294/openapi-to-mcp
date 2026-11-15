"""OpenAPI compatibility checks for constructs the mapper cannot execute."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote

from openapi_to_mcp.common.form_media import (
    FormMediaError,
    normalize_form_media,
    resolve_local,
    resolve_local_schema,
    schema_kind,
)

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
    invalid_array_ref: bool = False
    invalid_ref: bool = False


_INVALID_ARRAY_REF = object()


def openapi_operation_findings(  # noqa: C901, PLR0912, PLR0915
    spec: dict[str, Any], operation_ref: OperationRef
) -> list[OpenAPIFinding]:
    """Return unsupported OpenAPI constructs reachable from one operation."""
    findings: list[OpenAPIFinding] = []
    if operation_ref.origin == "additional":
        method = operation_ref.method
        if not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", method, re.ASCII):
            guidance = "Additional operation methods must be valid ASCII HTTP tokens."
        elif method != method.upper():
            guidance = "Additional operation methods must use uppercase ASCII; mixed-case methods cannot be faithfully executed."
        elif method in {
            "GET",
            "PUT",
            "POST",
            "DELETE",
            "OPTIONS",
            "HEAD",
            "PATCH",
            "TRACE",
            "QUERY",
        }:
            guidance = "This method is reserved for a fixed Path Item field."
        elif method == "CONNECT":
            guidance = "CONNECT tunnelling is not supported."
        else:
            guidance = None
        if guidance:
            findings.append(
                OpenAPIFinding("additionalOperations", operation_ref.location, guidance)
            )

    for candidates, location in (
        (
            operation_ref.path_item.get("parameters"),
            f"paths.{operation_ref.path}.parameters",
        ),
        (
            operation_ref.operation.get("parameters"),
            f"{operation_ref.location}.parameters",
        ),
    ):
        declared = _parameter_refs(spec, candidates, location)
        if sum(p.parameter.get("in") == "querystring" for p in declared) > 1:
            findings.append(
                OpenAPIFinding(
                    "in: querystring",
                    location,
                    "Multiple whole-query declarations are unsupported.",
                )
            )
    parameters = _effective_parameters(spec, operation_ref)
    whole = [p for p in parameters if p.parameter.get("in") == "querystring"]
    for parameter_ref in parameters:
        if parameter_ref.invalid_array_ref:
            findings.append(
                OpenAPIFinding(
                    "parameter $ref",
                    f"{parameter_ref.location}.$ref",
                    "The local parameter reference contains an invalid or out-of-range array index.",
                )
            )
        if parameter_ref.invalid_ref and "swagger" not in spec:
            findings.append(
                OpenAPIFinding(
                    "parameter $ref",
                    f"{parameter_ref.location}.$ref",
                    "External, cyclic or unresolved parameter references are unsupported.",
                )
            )
    for parameter_ref in whole:
        try:
            content = parameter_ref.parameter.get("content")
            if not isinstance(content, dict) or len(content) != 1:
                raise FormMediaError(  # noqa: TRY301
                    "Whole-query parameters require exactly one content media type."
                )
            content_type, media = next(iter(content.items()))
            media = resolve_local(spec, media)
            schema = resolve_local_schema(spec, media.get("schema"))
            if content_type == "application/x-www-form-urlencoded":
                normalize_form_media(spec, media)
            elif content_type == "text/plain":
                if not isinstance(schema, dict) or schema_kind(schema) != "string":
                    raise FormMediaError("Whole text queries require a string schema.")  # noqa: TRY301
            elif content_type != "application/json":
                raise FormMediaError("Unsupported whole-query media type.")  # noqa: TRY301
            if len(whole) > 1 or any(
                p.parameter.get("in") == "query" for p in parameters
            ):
                raise FormMediaError(  # noqa: TRY301
                    "A whole query cannot coexist with another whole or ordinary query parameter."
                )
            name = parameter_ref.parameter.get("name")
            if any(
                p is not parameter_ref and p.parameter.get("name") == name
                for p in parameters
            ) or (
                name == "requestBody"
                and operation_ref.operation.get("requestBody") is not None
            ):
                raise FormMediaError(  # noqa: TRY301
                    "The whole-query argument name collides with another input."
                )
        except FormMediaError as exc:
            findings.append(
                OpenAPIFinding(
                    "in: querystring", f"{parameter_ref.location}.in", str(exc)
                )
            )
    body = operation_ref.operation.get("requestBody")
    if body is not None:
        try:
            body = resolve_local(spec, body)
            content = body.get("content", {})
            if isinstance(content, dict) and content:
                selected = (
                    "application/json"
                    if isinstance(content.get("application/json"), dict)
                    else next(iter(content))
                )
                if selected == "application/x-www-form-urlencoded":
                    normalize_form_media(spec, content[selected])
                elif selected not in ("application/json", "text/plain"):
                    raise FormMediaError(  # noqa: TRY301
                        "Selected request-body media type is unsupported."
                    )
        except FormMediaError as exc:
            findings.append(
                OpenAPIFinding(
                    "requestBody", f"{operation_ref.location}.requestBody", str(exc)
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
            return _ParameterRef({}, current_location, invalid_ref=True)
        resolved = _resolve_local_ref(spec, ref)
        if resolved is _INVALID_ARRAY_REF:
            return _ParameterRef({}, current_location, invalid_array_ref=True)
        if not isinstance(resolved, dict):
            return _ParameterRef({}, current_location, invalid_ref=True)
        current = resolved
        current_location = _location_for_ref(ref)
    return _ParameterRef({}, current_location, invalid_ref=True)


def _parameter_key(parameter: dict[str, Any]) -> tuple[str, str] | None:
    name = parameter.get("name")
    location = parameter.get("in")
    if not isinstance(name, str) or not isinstance(location, str):
        return None
    return (name, location)


def _resolve_local_ref(spec: dict[str, Any], ref: str) -> object:
    current: object = spec
    for token in _local_ref_tokens(ref):
        if isinstance(current, dict):
            current = current.get(token)
        elif isinstance(current, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", token, re.ASCII):
                return _INVALID_ARRAY_REF
            try:
                index = int(token)
            except ValueError:
                return _INVALID_ARRAY_REF
            if index >= len(current):
                return _INVALID_ARRAY_REF
            current = current[index]
        else:
            return None
    return current


def _location_for_ref(ref: str) -> str:
    return ".".join(_local_ref_tokens(ref))


def _local_ref_tokens(ref: str) -> list[str]:
    """Decode the URI fragment before applying JSON Pointer token escaping."""
    return [
        token.replace("~1", "/").replace("~0", "~")
        for token in unquote(ref[2:]).split("/")
    ]
