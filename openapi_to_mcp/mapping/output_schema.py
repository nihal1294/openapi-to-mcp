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

# Only keywords whose conversion is understood here can contribute to an
# advertised output promise. Annotations are not traversed as schemas.
_ANNOTATIONS = frozenset(
    {
        "title",
        "description",
        "default",
        "examples",
        "example",
        "readOnly",
        "writeOnly",
        "deprecated",
        "externalDocs",
    }
)
_COMMON_KEYWORDS = frozenset(
    {"type", "enum", "const", "nullable", "$ref", "allOf", "anyOf"}
)
_OBJECT_KEYWORDS = frozenset({"properties", "required", "additionalProperties"})
_ARRAY_KEYWORDS = frozenset({"items", "minItems", "maxItems", "uniqueItems"})
_STRING_KEYWORDS = frozenset({"minLength", "maxLength", "pattern"})
_NUMBER_KEYWORDS = frozenset(
    {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf"}
)
_SUPPORTED_KEYWORDS = (
    _ANNOTATIONS
    | _COMMON_KEYWORDS
    | _OBJECT_KEYWORDS
    | _ARRAY_KEYWORDS
    | _STRING_KEYWORDS
    | _NUMBER_KEYWORDS
    | {"format"}
)
_KNOWN_STRING_FORMATS = frozenset(
    {
        "date",
        "date-time",
        "time",
        "duration",
        "email",
        "idn-email",
        "hostname",
        "idn-hostname",
        "ipv4",
        "ipv6",
        "uri",
        "uri-reference",
        "iri",
        "iri-reference",
        "uuid",
        "json-pointer",
        "relative-json-pointer",
        "regex",
        "byte",
        "binary",
        "password",
    }
)


def extract_output_schema(  # noqa: C901, PLR0911, PLR0912
    operation: dict[str, Any],
    spec: dict[str, Any],
    resolve_ref: Callable[[str], dict[str, Any]],
) -> dict[str, Any] | None:
    """Describe every documented success, or omit an unsafe output promise."""
    if (
        "jsonSchemaDialect" in spec
        or ("openapi" in spec and not str(spec["openapi"]).startswith(("3.0.", "3.1.")))
        or ("swagger" in spec and spec["swagger"] != "2.0")
    ):
        return None
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


def _has_unsafe_conversion(  # noqa: C901, PLR0911, PLR0912
    schema: dict[str, Any],
    resolve_ref: Callable[[str], dict[str, Any]],
    active_refs: set[str],
) -> bool:
    """Reject source schema semantics the converter cannot faithfully preserve."""
    if any(
        key not in _SUPPORTED_KEYWORDS and not key.startswith("x-") for key in schema
    ):
        return True
    if schema.get("writeOnly") is True:
        return True
    schema_type = schema.get("type")
    types = [schema_type] if isinstance(schema_type, str) else schema_type
    if types is not None and (
        not isinstance(types, list)
        or not types
        or not all(
            isinstance(t, str)
            and t
            in {"object", "array", "string", "integer", "number", "boolean", "null"}
            for t in types
        )
    ):
        return True
    types = types or []
    if schema.get("nullable") is True and not types:
        return True
    if any(key in schema for key in _OBJECT_KEYWORDS) and "object" not in types:
        return True
    if any(key in schema for key in _ARRAY_KEYWORDS) and "array" not in types:
        return True
    if any(key in schema for key in _STRING_KEYWORDS) and "string" not in types:
        return True
    if any(key in schema for key in _NUMBER_KEYWORDS) and not {
        "integer",
        "number",
    }.intersection(types):
        return True
    if "format" in schema:
        fmt = schema["format"]
        if "string" in types and (
            not isinstance(fmt, str) or fmt not in _KNOWN_STRING_FORMATS
        ):
            return True
        if not {"string", "number", "integer"}.intersection(types):
            return True
    ref = schema.get("$ref")
    if ref is not None:
        if not isinstance(ref, str) or not ref.startswith("#/") or ref in active_refs:
            return True
        # The converter merges siblings after dereferencing; avoid altered semantics.
        if any(
            key not in _ANNOTATIONS and key != "$ref" and not key.startswith("x-")
            for key in schema
        ):
            return True
        resolved = resolve_ref(ref)
        if not isinstance(resolved, dict) or _has_unsafe_conversion(
            resolved, resolve_ref, active_refs | {ref}
        ):
            return True
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return True
    children = list(properties.values())
    children.extend(
        schema[key] for key in ("items", "additionalProperties") if key in schema
    )
    for key in ("allOf", "anyOf"):
        if key in schema:
            branches = schema[key]
            if not isinstance(branches, list) or not branches:
                return True
            children.extend(branches)
    return any(
        not isinstance(child, (dict, bool))
        or (
            isinstance(child, dict)
            and _has_unsafe_conversion(child, resolve_ref, active_refs)
        )
        for child in children
    )


def _has_resolution_error(schema: dict[str, Any]) -> bool:
    description = schema.get("description")
    if isinstance(description, str) and description.startswith(
        (
            "Unresolved reference:",
            "Resolved reference is not an object:",
            "Cyclic reference detected:",
        )
    ):
        return True
    children: list[object] = []
    properties = schema.get("properties")
    if isinstance(properties, dict):
        children.extend(properties.values())
    children.extend(schema.get(key) for key in ("items", "additionalProperties", "not"))
    for key in ("allOf", "anyOf", "oneOf"):
        branches = schema.get(key)
        if isinstance(branches, list):
            children.extend(branches)
    return any(
        isinstance(child, dict) and _has_resolution_error(child) for child in children
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
