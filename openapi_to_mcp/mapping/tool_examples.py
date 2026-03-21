"""Helpers for shaping MCP tool input examples from OpenAPI metadata."""

from __future__ import annotations

from typing import Any

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


def add_parameter_example(param: dict[str, Any], schema: dict[str, Any]) -> None:
    """Attach parameter-level OpenAPI examples to a converted parameter schema."""
    explicit_example = _extract_explicit_example(param)
    if explicit_example is None:
        return
    schema["examples"] = [explicit_example]


def add_media_example(media: dict[str, Any], schema: dict[str, Any]) -> None:
    """Attach request-body media examples to a converted request body schema."""
    explicit_example = _extract_explicit_example(media)
    if explicit_example is None:
        return
    schema["examples"] = [explicit_example]


def build_input_examples(
    input_schema: dict[str, Any],
) -> list[dict[str, JsonValue]] | None:
    """Build a top-level input example object from shaped property examples."""
    if input_schema.get("type") != "object":
        return None

    properties = input_schema.get("properties")
    if not isinstance(properties, dict):
        return None

    example_object = {
        name: example
        for name, schema in properties.items()
        for example in [_build_schema_example(schema)]
        if example is not None
    }
    if not example_object:
        return None
    return [example_object]


def _build_schema_example(schema_maybe: object) -> JsonValue | None:
    if not isinstance(schema_maybe, dict):
        return None

    scalar_example = _first_scalar_example(schema_maybe)
    if scalar_example is not None:
        return scalar_example

    schema_type = schema_maybe.get("type")
    if schema_type == "object":
        return _build_object_example(schema_maybe)
    if schema_type == "array":
        item_example = _build_schema_example(schema_maybe.get("items"))
        if item_example is None:
            return None
        return [item_example]
    return None


def _build_object_example(schema: dict[str, Any]) -> dict[str, JsonValue] | None:
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return None

    example_object = {
        name: example
        for name, prop_schema in properties.items()
        for example in [_build_schema_example(prop_schema)]
        if example is not None
    }
    return example_object or None


def _extract_explicit_example(source: dict[str, Any]) -> JsonValue | None:
    if "example" in source:
        return source["example"]

    examples = source.get("examples")
    if not isinstance(examples, dict):
        return None

    for example in examples.values():
        if not isinstance(example, dict):
            continue
        if "value" in example:
            return example["value"]
    return None


def _first_scalar_example(schema: dict[str, Any]) -> JsonValue | None:
    examples = schema.get("examples")
    if isinstance(examples, list) and examples:
        return examples[0]
    if "default" in schema:
        return schema["default"]
    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]
    return None
