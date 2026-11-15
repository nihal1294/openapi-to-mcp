"""Helpers for extracting MCP tool output schemas from OpenAPI responses."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from openapi_to_mcp.common.exceptions import SchemaError
from openapi_to_mcp.schema.converter import openapi_schema_to_json_schema

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)
_HTTP_STATUS_CODE_LENGTH = 3


def extract_output_schema(  # noqa: C901, PLR0911, PLR0912
    operation: dict[str, Any],
    spec: dict[str, Any],
    resolve_ref: Callable[[str], dict[str, Any]],
) -> dict[str, Any] | None:
    """Describe every documented success, or omit an unsafe output promise."""
    responses = operation.get("responses")
    if not isinstance(responses, dict):
        return None
    codes = sorted(
        code for code in responses if isinstance(code, str) and _may_be_success(code)
    )
    if not codes:
        return None
    schemas: list[dict[str, Any]] = []
    for code in codes:
        if code.lower() in {"204", "205", "2xx", "default"}:
            return None
        response = responses[code]
        if isinstance(response, dict) and isinstance(response.get("$ref"), str):
            response = resolve_ref(response["$ref"])
        if not isinstance(response, dict):
            return None
        raw_schemas = _response_schemas(response, operation, spec)
        if not raw_schemas:
            return None
        for schema in raw_schemas:
            if (
                _possibly_nullable(schema, resolve_ref, set())
                or not _raw_object_guarantee(schema, resolve_ref, set())
                or _has_unsafe_conversion(schema, resolve_ref, set())
            ):
                return None
            try:
                converted = openapi_schema_to_json_schema(
                    schema, spec, raise_on_error=True
                )
            except SchemaError:
                logger.warning(
                    "Skipping outputSchema because response schema conversion failed."
                )
                return None
            if _has_resolution_error(converted) or not _supports_structured_output(
                converted
            ):
                return None
            if "type" not in converted:
                converted = {"type": "object", **converted}
            if converted not in schemas:
                schemas.append(converted)
    if len(schemas) == 1:
        return schemas[0]
    return {"type": "object", "anyOf": schemas}


def _may_be_success(code: str) -> bool:
    return code.lower() in {"2xx", "default"} or (
        len(code) == _HTTP_STATUS_CODE_LENGTH
        and code.isascii()
        and code.isdigit()
        and code.startswith("2")
    )


def _is_json(media_type: object) -> bool:
    return isinstance(media_type, str) and "json" in media_type


def _response_schemas(  # noqa: PLR0911
    response: dict[str, Any], operation: dict[str, Any], spec: dict[str, Any]
) -> list[dict[str, Any]] | None:
    if "content" in response:
        content = response["content"]
        if not isinstance(content, dict) or not content:
            return None
        schemas = []
        if not all(isinstance(key, str) for key in content):
            return None
        for media_type in sorted(content):
            media = content[media_type]
            if not _is_json(media_type) or not isinstance(media, dict):
                return None
            schema = media.get("schema")
            if not isinstance(schema, dict) or not schema:
                return None
            schemas.append(schema)
        return schemas
    produces = operation.get("produces", spec.get("produces"))
    if produces is not None and (
        not isinstance(produces, list)
        or not produces
        or not all(map(_is_json, produces))
    ):
        return None
    schema = response.get("schema")
    return [schema] if isinstance(schema, dict) and schema else None


def _possibly_nullable(
    schema: dict[str, Any],
    resolve_ref: Callable[[str], dict[str, Any]],
    active_refs: set[str],
) -> bool:
    # Nullable composition can be lost during conversion when no type is stated.
    if schema.get("nullable") is True:
        return True
    ref = schema.get("$ref")
    if isinstance(ref, str):
        if ref in active_refs:
            return True
        resolved = resolve_ref(ref)
        if not isinstance(resolved, dict) or not resolved:
            return True
        if _possibly_nullable(resolved, resolve_ref, active_refs | {ref}):
            return True
    for key in ("allOf", "anyOf", "oneOf"):
        branches = schema.get(key)
        if isinstance(branches, list) and any(
            isinstance(branch, dict)
            and _possibly_nullable(branch, resolve_ref, active_refs)
            for branch in branches
        ):
            return True
    return False


def _raw_object_guarantee(
    schema: dict[str, Any],
    resolve_ref: Callable[[str], dict[str, Any]],
    active_refs: set[str],
) -> bool:
    """Prove object shape from source constraints rather than inferred types."""
    schema_type = schema.get("type")
    if schema_type is not None:
        return schema_type in ("object", ["object"])
    ref = schema.get("$ref")
    if isinstance(ref, str) and ref not in active_refs:
        resolved = resolve_ref(ref)
        if isinstance(resolved, dict) and _raw_object_guarantee(
            resolved, resolve_ref, active_refs | {ref}
        ):
            return True
    for key in ("anyOf", "oneOf"):
        branches = schema.get(key)
        if (
            isinstance(branches, list)
            and branches
            and all(
                isinstance(item, dict)
                and _raw_object_guarantee(item, resolve_ref, active_refs)
                for item in branches
            )
        ):
            return True
    branches = schema.get("allOf")
    return isinstance(branches, list) and any(
        isinstance(item, dict) and _raw_object_guarantee(item, resolve_ref, active_refs)
        for item in branches
    )


def _has_unsafe_conversion(
    schema: dict[str, Any],
    resolve_ref: Callable[[str], dict[str, Any]],
    active_refs: set[str],
) -> bool:
    """Avoid conversions that may narrow the set of valid response values."""
    # Lost constraints can turn exclusive branches into overlaps, or make a
    # negated schema broader, rejecting values accepted by the source schema.
    if "oneOf" in schema or "not" in schema:
        return True
    if "type" not in schema and ("properties" in schema or "items" in schema):
        return True
    ref = schema.get("$ref")
    if isinstance(ref, str):
        if ref in active_refs:
            return True
        resolved = resolve_ref(ref)
        if not isinstance(resolved, dict) or _has_unsafe_conversion(
            resolved, resolve_ref, active_refs | {ref}
        ):
            return True
    children: list[object] = []
    for key in ("properties", "patternProperties", "$defs", "definitions"):
        mapping = schema.get(key)
        if isinstance(mapping, dict):
            children.extend(mapping.values())
    children.extend(schema.get(key) for key in ("items", "additionalProperties", "not"))
    for key in ("allOf", "anyOf", "oneOf", "prefixItems"):
        branches = schema.get(key)
        if isinstance(branches, list):
            children.extend(branches)
    return any(
        isinstance(child, dict)
        and _has_unsafe_conversion(child, resolve_ref, active_refs)
        for child in children
    )


def _has_resolution_error(value: object) -> bool:
    if isinstance(value, dict):
        description = value.get("description")
        if isinstance(description, str) and description.startswith(
            (
                "Unresolved reference:",
                "Resolved reference is not an object:",
                "Cyclic reference detected:",
            )
        ):
            return True
        return any(_has_resolution_error(child) for child in value.values())
    return isinstance(value, list) and any(
        _has_resolution_error(child) for child in value
    )


def _supports_structured_output(schema: dict[str, Any]) -> bool:
    """Return whether every value admitted by the schema is an object."""
    schema_type = schema.get("type")
    if schema_type is not None:
        return schema_type in ("object", ["object"])
    if "properties" in schema:
        # The converter infers an object type for properties.
        return False
    for key in ("anyOf", "oneOf"):
        branches = schema.get(key)
        if (
            isinstance(branches, list)
            and branches
            and all(
                isinstance(item, dict) and _supports_structured_output(item)
                for item in branches
            )
        ):
            return True
    branches = schema.get("allOf")
    return isinstance(branches, list) and any(
        isinstance(item, dict) and _supports_structured_output(item)
        for item in branches
    )
