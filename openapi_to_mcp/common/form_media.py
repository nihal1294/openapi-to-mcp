"""Normalize the supported URL-encoded media subset for diagnostics and runtime."""

from __future__ import annotations

import math
from typing import Any
from urllib.parse import unquote


class FormMediaError(ValueError):
    """An encoding cannot be represented by the form runtime."""


def resolve_local(
    spec: dict[str, Any], value: object, *, form_schema_mode: str | None = None
) -> dict[str, Any]:
    """Resolve a local reference whose target must be an object."""
    resolved = _resolve_local(spec, value, form_schema_mode=form_schema_mode)
    if not isinstance(resolved, dict):
        raise FormMediaError("Missing or invalid local reference or schema.")
    return resolved


def resolve_local_schema(spec: dict[str, Any], value: object) -> dict[str, Any] | bool:
    """Resolve a local schema reference, including boolean schema targets."""
    return _resolve_local(spec, value)


def _resolve_local(  # noqa: C901
    spec: dict[str, Any], value: object, *, form_schema_mode: str | None = None
) -> dict[str, Any] | bool:
    """Resolve a bounded chain of local JSON Pointer references."""
    seen: set[str] = set()
    while isinstance(value, dict) and "$ref" in value:
        if form_schema_mode == "composed":
            if set(value) != {"$ref"}:
                raise FormMediaError("Composed form references must be pure.")
        elif form_schema_mode is not None:
            _check_form_schema(value, form_schema_mode, reference=True)
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
    if not isinstance(value, (dict, bool)):
        raise FormMediaError("Missing or invalid local reference or schema.")
    if form_schema_mode not in (None, "composed") and isinstance(value, dict):
        _check_form_schema(value, form_schema_mode, reference=False)
    return value


def schema_kind(schema: dict[str, Any]) -> object:
    kind = schema.get("type")
    if isinstance(kind, list) and len(kind) == 2 and kind.count("null") == 1:  # noqa: PLR2004
        return next(item for item in kind if item != "null")
    return kind


def _is_binary(schema: dict[str, Any]) -> bool:
    return any(
        key in schema for key in ("contentEncoding", "contentMediaType")
    ) or schema.get("format") in ("binary", "byte")


def _reject_composed_layout(schema: dict[str, Any]) -> None:
    if any(keyword in schema for keyword in ("allOf", "oneOf", "anyOf")):
        raise FormMediaError("Composed form object layouts are unsupported.")
    dependencies = schema.get("dependencies")
    if any(
        keyword in schema
        for keyword in ("patternProperties", "dependentSchemas", "if", "then", "else")
    ) or (
        isinstance(dependencies, dict)
        and any(isinstance(value, dict) for value in dependencies.values())
    ):
        raise FormMediaError(
            "Pattern, conditional and dependent form object layouts are unsupported."
        )


def _check_form_schema(schema: dict[str, Any], mode: str, *, reference: bool) -> None:
    if _is_binary(schema):
        raise FormMediaError("Binary form fields are unsupported.")
    if mode == "expanded":
        _reject_composed_layout(schema)
    if reference:
        shape_keys = {"type", "items", "prefixItems"}
        if mode == "expanded":
            shape_keys.update(
                {"properties", "additionalProperties", "required", "patternProperties"}
            )
        if shape_keys.intersection(schema):
            raise FormMediaError(
                "Form schema reference siblings affecting serialization are unsupported."
            )


def _field(spec: dict[str, Any], schema: object, encoding: object) -> dict[str, Any]:  # noqa: C901, PLR0912
    original_schema = schema
    schema = resolve_local(spec, schema)
    if not isinstance(encoding, dict):
        raise FormMediaError("Invalid Encoding Object.")
    if any(key in encoding for key in ("encoding", "prefixEncoding", "itemEncoding")):
        raise FormMediaError("Nested form encoding is unsupported.")
    if encoding.get("allowReserved") is True:
        raise FormMediaError("allowReserved=true is unsupported for forms.")
    kind = schema_kind(schema)
    if kind not in ("string", "number", "integer", "boolean", "object", "array"):
        raise FormMediaError("Form fields need a supported explicit type.")
    style = any(key in encoding for key in ("style", "explode", "allowReserved"))
    mode = (
        "expanded"
        if style and kind == "object"
        else "opaque"
        if kind == "object"
        else "value"
    )
    schema = resolve_local(spec, original_schema, form_schema_mode=mode)
    item_kind = None
    if kind == "array":
        item = resolve_local(spec, schema.get("items"), form_schema_mode="value")
        item_kind = schema_kind(item)
        if item_kind not in ("string", "number", "integer", "boolean") or _is_binary(
            item
        ):
            raise FormMediaError("Form arrays require primitive items.")
    if style and encoding.get("style", "form") != "form":
        raise FormMediaError("Only form style is supported.")
    object_fields: dict[str, object] | None = None
    object_additional = None
    if style and kind == "object":
        props = schema.get("properties", {})
        if not isinstance(props, dict) or any(
            schema_kind(resolve_local(spec, p, form_schema_mode="value"))
            not in ("string", "number", "integer", "boolean")
            for p in props.values()
        ):
            raise FormMediaError("Styled objects require flat primitive properties.")
        children = {
            name: resolve_local(spec, prop, form_schema_mode="value")
            for name, prop in props.items()
        }
        if any(_is_binary(child) for child in children.values()):
            raise FormMediaError("Binary form fields are unsupported.")
        object_fields = {name: schema_kind(child) for name, child in children.items()}
        additional_schema = schema.get("additionalProperties")
        if isinstance(additional_schema, dict):
            resolved_additional = resolve_local(
                spec, additional_schema, form_schema_mode="value"
            )
            if _is_binary(resolved_additional):
                raise FormMediaError("Binary form fields are unsupported.")
            object_additional = schema_kind(resolved_additional)
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


def _composed_scalar_matches(kind: str, value: object) -> bool:
    if kind == "string":
        return isinstance(value, str)
    if kind == "boolean":
        return isinstance(value, bool)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if isinstance(value, float) and not math.isfinite(value):
        return False
    return kind == "number" or isinstance(value, int) or value.is_integer()


def _check_composed_field(spec: dict[str, Any], value: object) -> None:  # noqa: C901, PLR0912
    field = resolve_local(spec, value, form_schema_mode="composed")
    kind = field.get("type")
    if kind not in ("string", "integer", "number", "boolean"):
        raise FormMediaError("Composed form fields need explicit scalar types.")
    common = {
        "type",
        "title",
        "description",
        "default",
        "example",
        "examples",
        "deprecated",
        "readOnly",
        "writeOnly",
        "enum",
        "const",
    }
    specific = (
        {"minLength", "maxLength", "pattern"}
        if kind == "string"
        else {"minimum", "maximum", "multipleOf"}
        if kind in ("number", "integer")
        else set()
    )
    if set(field) - common - specific:
        raise FormMediaError("Composed form field has unsupported keywords.")
    for key in ("title", "description", "pattern"):
        if key in field and not isinstance(field[key], str):
            raise FormMediaError("Invalid composed form string annotation or pattern.")
    for key in ("deprecated", "readOnly", "writeOnly"):
        if key in field and not isinstance(field[key], bool):
            raise FormMediaError("Invalid composed form annotation.")
    for key in ("minLength", "maxLength"):
        if key in field and (
            isinstance(field[key], bool)
            or not isinstance(field[key], int)
            or field[key] < 0
        ):
            raise FormMediaError("Invalid composed form length.")
    for key in ("minimum", "maximum", "multipleOf"):
        if key in field and (
            not _composed_scalar_matches("number", field[key])
            or (key == "multipleOf" and field[key] <= 0)
        ):
            raise FormMediaError("Invalid composed form numeric constraint.")
    for key in ("default", "example", "const"):
        if key in field and not _composed_scalar_matches(kind, field[key]):
            raise FormMediaError("Invalid composed form scalar value.")
    for key in ("enum", "examples"):
        if key in field:
            values = field[key]
            if (
                not isinstance(values, list)
                or (key == "enum" and not values)
                or any(not _composed_scalar_matches(kind, item) for item in values)
            ):
                raise FormMediaError("Invalid composed form scalar values.")
            if key == "enum" and any(
                item in values[:i] for i, item in enumerate(values)
            ):
                raise FormMediaError("Duplicate composed form enum value.")


def _composed_properties(spec: dict[str, Any], source: object) -> dict[str, Any]:
    root = resolve_local(spec, source, form_schema_mode="composed")
    if (
        set(root) - {"type", "allOf", "title", "description"}
        or root.get("type") != "object"
        or not isinstance(root.get("allOf"), list)
        or not root["allOf"]
    ):
        raise FormMediaError("Composed form object layout is unsupported.")
    properties: dict[str, Any] = {}
    for node in [root, *root["allOf"]]:
        branch = (
            root
            if node is root
            else resolve_local(spec, node, form_schema_mode="composed")
        )
        if any(
            key in branch and not isinstance(branch[key], str)
            for key in ("title", "description")
        ):
            raise FormMediaError("Invalid composed form description.")
        if node is root:
            continue
        if (
            set(branch) - {"type", "properties", "required", "title", "description"}
            or branch.get("type") != "object"
            or not isinstance(branch.get("properties"), dict)
        ):
            raise FormMediaError("Composed form branch is unsupported.")
        fields = branch["properties"]
        required = branch.get("required", [])
        if (
            not isinstance(required, list)
            or any(not isinstance(name, str) for name in required)
            or len(set(required)) != len(required)
            or any(name not in fields for name in required)
            or any(not isinstance(name, str) or name in properties for name in fields)
        ):
            raise FormMediaError("Invalid or overlapping composed form properties.")
        for name, field in fields.items():
            _check_composed_field(spec, field)
            properties[name] = field
    return properties


def normalize_form_media(spec: dict[str, Any], media: object) -> dict[str, Any]:
    """Return a narrow, JSON-serializable description of supported form encoding."""
    media = resolve_local(spec, media)
    if "itemEncoding" in media or "prefixEncoding" in media:
        raise FormMediaError("Nested form encoding is unsupported.")
    source = media.get("schema")
    schema = resolve_local(spec, source)
    composed = "allOf" in schema
    if composed:
        properties = _composed_properties(spec, source)
    else:
        schema = resolve_local(spec, source, form_schema_mode="expanded")
        properties = schema.get("properties", {})
    if schema_kind(schema) != "object":
        raise FormMediaError("Form media requires an object schema.")
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
