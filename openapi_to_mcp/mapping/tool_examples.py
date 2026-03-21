"""Helpers for shaping MCP tool input examples from OpenAPI metadata."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


class _MissingType:
    """Sentinel type for missing examples."""


_MISSING = _MissingType()
type ExampleResult = JsonValue | _MissingType


def add_parameter_example(
    param: dict[str, Any],
    schema: dict[str, Any],
    resolve_ref: Callable[[str], dict[str, Any]],
) -> None:
    """Attach parameter-level OpenAPI examples to a converted parameter schema."""
    explicit_example = _extract_explicit_example(param, resolve_ref)
    if explicit_example is _MISSING:
        return
    schema["examples"] = [explicit_example]


def add_media_example(
    media: dict[str, Any],
    schema: dict[str, Any],
    resolve_ref: Callable[[str], dict[str, Any]],
) -> None:
    """Attach request-body media examples to a converted request body schema."""
    explicit_example = _extract_explicit_example(media, resolve_ref)
    if explicit_example is _MISSING:
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
        if example is not _MISSING
    }
    if not example_object:
        return None
    return [example_object]


def _build_schema_example(schema_maybe: object) -> ExampleResult:
    if not isinstance(schema_maybe, dict):
        return _MISSING

    scalar_example = _first_scalar_example(schema_maybe)
    if scalar_example is not _MISSING:
        return scalar_example

    schema_type = schema_maybe.get("type")
    if schema_type == "object":
        return _build_object_example(schema_maybe)
    if schema_type == "array":
        item_example = _build_schema_example(schema_maybe.get("items"))
        if item_example is _MISSING:
            return _MISSING
        return [item_example]
    return _MISSING


def _build_object_example(schema: dict[str, Any]) -> ExampleResult:
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return _MISSING

    example_object = {
        name: example
        for name, prop_schema in properties.items()
        for example in [_build_schema_example(prop_schema)]
        if example is not _MISSING
    }
    if not example_object:
        return _MISSING
    return example_object


def _extract_explicit_example(
    source: dict[str, Any],
    resolve_ref: Callable[[str], dict[str, Any]],
) -> ExampleResult:
    if "example" in source:
        return source["example"]

    examples = source.get("examples")
    if not isinstance(examples, dict):
        return _MISSING

    for example_maybe_ref in examples.values():
        example = _resolve_example_ref(example_maybe_ref, resolve_ref)
        if "value" in example:
            return example["value"]
    return _MISSING


def _first_scalar_example(schema: dict[str, Any]) -> ExampleResult:
    examples = schema.get("examples")
    if isinstance(examples, list) and examples:
        return examples[0]
    if "default" in schema:
        return schema["default"]
    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]
    return _MISSING


def _resolve_example_ref(
    example_maybe_ref: object,
    resolve_ref: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(example_maybe_ref, dict):
        return {}
    ref_path = example_maybe_ref.get("$ref")
    if not isinstance(ref_path, str):
        return example_maybe_ref
    resolved = resolve_ref(ref_path)
    if not isinstance(resolved, dict):
        return {}
    return resolved
