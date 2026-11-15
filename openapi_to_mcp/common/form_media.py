"""Normalize the supported URL-encoded media subset for diagnostics and runtime."""

from __future__ import annotations

from typing import Any
from urllib.parse import unquote


class FormMediaError(ValueError):
    """An encoding cannot be represented by the form runtime."""


def resolve_local(spec: dict[str, Any], value: object) -> dict[str, Any]:
    """Resolve a bounded chain of local JSON Pointer references."""
    seen: set[str] = set()
    while isinstance(value, dict) and "$ref" in value:
        ref = value["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/") or ref in seen:
            raise FormMediaError(
                "External, cyclic or invalid reference is unsupported."
            )
        seen.add(ref)
        current: object = spec
        for raw_segment in unquote(ref[2:]).split("/"):
            segment = raw_segment.replace("~1", "/").replace("~0", "~")
            if isinstance(current, dict):
                current = current.get(segment)
            elif (
                isinstance(current, list)
                and segment.isascii()
                and segment.isdecimal()
                and (segment == "0" or not segment.startswith("0"))
            ):
                index = int(segment)
                current = current[index] if index < len(current) else None
            else:
                current = None
        value = current
    if not isinstance(value, dict):
        raise FormMediaError("Missing or invalid local reference or schema.")
    return value


def schema_kind(schema: dict[str, Any]) -> object:
    kind = schema.get("type")
    if isinstance(kind, list) and len(kind) == 2 and kind.count("null") == 1:  # noqa: PLR2004
        return next(item for item in kind if item != "null")
    return kind


def _field(spec: dict[str, Any], schema: object, encoding: object) -> dict[str, Any]:  # noqa: C901, PLR0912
    schema = resolve_local(spec, schema)
    if not isinstance(encoding, dict):
        raise FormMediaError("Invalid Encoding Object.")
    if any(key in encoding for key in ("encoding", "prefixEncoding", "itemEncoding")):
        raise FormMediaError("Nested form encoding is unsupported.")
    if encoding.get("allowReserved") is True:
        raise FormMediaError("allowReserved=true is unsupported for forms.")
    if any(
        key in schema for key in ("contentEncoding", "contentMediaType")
    ) or schema.get("format") in ("binary", "byte"):
        raise FormMediaError("Binary form fields are unsupported.")
    kind = schema_kind(schema)
    if kind not in ("string", "number", "integer", "boolean", "object", "array"):
        raise FormMediaError("Form fields need a supported explicit type.")
    item_kind = None
    if kind == "array":
        item = resolve_local(spec, schema.get("items"))
        item_kind = schema_kind(item)
        if (
            item_kind not in ("string", "number", "integer", "boolean")
            or item.get("format") in ("binary", "byte")
            or "contentEncoding" in item
            or "contentMediaType" in item
        ):
            raise FormMediaError("Form arrays require primitive items.")
    style = any(key in encoding for key in ("style", "explode", "allowReserved"))
    if style and encoding.get("style", "form") != "form":
        raise FormMediaError("Only form style is supported.")
    object_fields: dict[str, object] | None = None
    object_additional = None
    if style and kind == "object":
        props = schema.get("properties", {})
        if not isinstance(props, dict) or any(
            schema_kind(resolve_local(spec, p))
            not in ("string", "number", "integer", "boolean")
            for p in props.values()
        ):
            raise FormMediaError("Styled objects require flat primitive properties.")
        object_fields = {
            name: schema_kind(resolve_local(spec, prop)) for name, prop in props.items()
        }
        additional_schema = schema.get("additionalProperties")
        if isinstance(additional_schema, dict):
            object_additional = schema_kind(resolve_local(spec, additional_schema))
            if object_additional not in ("string", "number", "integer", "boolean"):
                raise FormMediaError(
                    "Styled object additional properties must be primitive."
                )
    content_type = encoding.get(
        "contentType", "application/json" if kind == "object" else "text/plain"
    )
    if not style and (
        content_type not in ("application/json", "text/plain")
        or (content_type == "text/plain" and kind == "object")
    ):
        raise FormMediaError("Unsupported form field contentType.")
    explode = encoding.get("explode", True)
    if not isinstance(explode, bool) or (
        "allowReserved" in encoding and not isinstance(encoding["allowReserved"], bool)
    ):
        raise FormMediaError("Invalid form encoding flag.")
    return {
        "kind": kind,
        "itemKind": item_kind,
        "mode": "style" if style else "content",
        "contentType": content_type if not style else None,
        "explode": explode,
        **(
            {"objectFields": object_fields, "objectAdditional": object_additional}
            if object_fields is not None
            else {}
        ),
    }


def normalize_form_media(spec: dict[str, Any], media: object) -> dict[str, Any]:
    """Return a narrow, JSON-serializable description of supported form encoding."""
    media = resolve_local(spec, media)
    if "itemEncoding" in media or "prefixEncoding" in media:
        raise FormMediaError("Nested form encoding is unsupported.")
    schema = resolve_local(spec, media.get("schema"))
    if schema_kind(schema) != "object":
        raise FormMediaError("Form media requires an object schema.")
    properties = schema.get("properties", {})
    encodings = media.get("encoding", {})
    if not isinstance(properties, dict) or not isinstance(encodings, dict):
        raise FormMediaError("Invalid form properties or encoding.")
    additional = schema.get("additionalProperties")
    if any(name not in properties for name in encodings) and not isinstance(
        additional, dict
    ):
        raise FormMediaError(
            "Encoding names require declared properties or a supported additionalProperties schema."
        )
    fields = {
        name: _field(spec, field, encodings.get(name, {}))
        for name, field in properties.items()
    }
    for name, encoding in encodings.items():
        if name not in properties:
            fields[name] = _field(spec, additional, encoding)
    return {
        "version32": str(spec.get("openapi", "")).startswith("3.2."),
        "fields": fields,
        "additional": _field(spec, additional, {})
        if isinstance(additional, dict)
        else None,
    }
