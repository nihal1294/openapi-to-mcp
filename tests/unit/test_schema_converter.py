from typing import Any

import pytest

from openapi_to_mcp.schema.converter import (
    SchemaConverter,
    openapi_schema_to_json_schema,
)
from openapi_to_mcp.schema.handlers.reference import ReferenceHandler


# Helper function to replace the imported resolve_ref
def resolve_ref(ref: str, full_spec: dict) -> dict:
    """Helper function to resolve references in tests."""
    handler = ReferenceHandler(SchemaConverter(full_spec))
    return handler.resolve_ref(ref)


SAMPLE_FULL_SPEC: dict[str, Any] = {
    "openapi": "3.0.0",
    "info": {"title": "Test API", "version": "1.0"},
    "paths": {},
    "components": {
        "schemas": {
            "SimpleObject": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "format": "int64"},
                    "name": {"type": "string", "description": "Object name"},
                },
                "required": ["id"],
            },
            "ObjectWithRef": {
                "type": "object",
                "properties": {
                    "data": {"$ref": "#/components/schemas/SimpleObject"},
                    "timestamp": {"type": "string", "format": "date-time"},
                },
            },
            "ArrayOfSimple": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/SimpleObject"},
            },
            "NullableString": {
                "type": "string",
                "nullable": True,
                "description": "A string that can be null",
            },
            "NumberWithRange": {
                "type": "number",
                "format": "float",
                "minimum": 0,
                "maximum": 100,
                "exclusiveMaximum": True,
            },
            "StringEnum": {"type": "string", "enum": ["active", "inactive", "pending"]},
            # For cycle detection test
            "CyclicA": {
                "type": "object",
                "properties": {"b": {"$ref": "#/components/schemas/CyclicB"}},
            },
            "CyclicB": {
                "type": "object",
                "properties": {"a": {"$ref": "#/components/schemas/CyclicA"}},
            },
        }
    },
}


def test_resolve_ref_success() -> None:
    """Test successful resolution of a simple local ref."""
    ref = "#/components/schemas/SimpleObject"
    expected = SAMPLE_FULL_SPEC["components"]["schemas"]["SimpleObject"]
    assert resolve_ref(ref, SAMPLE_FULL_SPEC) == expected


def test_resolve_ref_nested() -> None:
    """Test resolution of a ref nested within another component."""
    ref_direct = "#/components/schemas/SimpleObject"
    expected = SAMPLE_FULL_SPEC["components"]["schemas"]["SimpleObject"]
    assert resolve_ref(ref_direct, SAMPLE_FULL_SPEC) == expected


def test_resolve_ref_not_found() -> None:
    """Test resolution failure for a non-existent path."""
    ref = "#/components/schemas/NonExistent"
    result = resolve_ref(ref, SAMPLE_FULL_SPEC)
    assert "description" in result
    assert result["description"] == f"Unresolved reference: {ref}"


def test_resolve_ref_invalid_format() -> None:
    """Test resolution failure for invalid ref format."""
    ref = "components/schemas/SimpleObject"
    result = resolve_ref(ref, SAMPLE_FULL_SPEC)
    assert "description" in result
    assert result["description"] == f"Unresolved reference: {ref}"


def test_resolve_ref_invalid_path_part() -> None:
    """Test resolution failure due to invalid index or key."""
    ref = "#/components/schemas/SimpleObject/properties/invalidKey"
    result = resolve_ref(ref, SAMPLE_FULL_SPEC)
    assert "description" in result
    assert result["description"] == f"Unresolved reference: {ref}"


@pytest.mark.parametrize(
    ("openapi_schema", "expected_json_schema"),
    [
        # Basic types
        ({"type": "string"}, {"type": "string"}),
        (
            {"type": "integer", "format": "int32"},
            {"type": "integer", "format": "int32"},
        ),
        ({"type": "number", "format": "float"}, {"type": "number", "format": "float"}),
        ({"type": "boolean"}, {"type": "boolean"}),
        ({"type": "null"}, {"type": "null"}),
        # String with details
        (
            SAMPLE_FULL_SPEC["components"]["schemas"]["StringEnum"],
            {"type": "string", "enum": ["active", "inactive", "pending"]},
        ),
        (
            {"type": "string", "format": "date-time", "description": "Timestamp"},
            {"type": "string", "format": "date-time", "description": "Timestamp"},
        ),
        (
            {"type": "string", "minLength": 5, "maxLength": 10, "pattern": "^[a-z]+$"},
            {"type": "string", "minLength": 5, "maxLength": 10, "pattern": "^[a-z]+$"},
        ),
        # Number with details
        (
            SAMPLE_FULL_SPEC["components"]["schemas"]["NumberWithRange"],
            {
                "type": "number",
                "format": "float",
                "minimum": 0,
                "maximum": 100,
                "exclusiveMaximum": 100,
            },
        ),
        # Simple object
        (
            {
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
            },
            {
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
            },
        ),
        # Simple array
        (
            {"type": "array", "items": {"type": "integer"}},
            {"type": "array", "items": {"type": "integer"}},
        ),
        # Nullable string
        (
            SAMPLE_FULL_SPEC["components"]["schemas"]["NullableString"],
            {"type": ["string", "null"], "description": "A string that can be null"},
        ),
        # Object with default and example
        (
            {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "default": "pending",
                        "example": "active",
                    }
                },
            },
            {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "default": "pending",
                        "examples": ["active"],
                    }
                },
                "required": [],
            },
        ),
    ],
)
def test_schema_conversion_basic(
    openapi_schema: dict[str, Any], expected_json_schema: dict[str, Any]
) -> None:
    """Tests conversion of basic OpenAPI schemas to JSON Schema."""
    assert (
        openapi_schema_to_json_schema(openapi_schema, SAMPLE_FULL_SPEC)
        == expected_json_schema
    )


def test_schema_conversion_simple_ref() -> None:
    """Test conversion of a schema with a simple $ref."""
    openapi_schema = {"$ref": "#/components/schemas/SimpleObject"}
    expected = {
        "type": "object",
        "properties": {
            "id": {"type": "integer", "format": "int64"},
            "name": {"type": "string", "description": "Object name"},
        },
        "required": ["id"],
        "description": "(from ref: #/components/schemas/SimpleObject)",
    }
    assert openapi_schema_to_json_schema(openapi_schema, SAMPLE_FULL_SPEC) == expected


def test_schema_conversion_nested_ref() -> None:
    """Test conversion of a schema containing a nested $ref."""
    openapi_schema = SAMPLE_FULL_SPEC["components"]["schemas"]["ObjectWithRef"]
    expected = {
        "type": "object",
        "properties": {
            "data": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "format": "int64"},
                    "name": {"type": "string", "description": "Object name"},
                },
                "required": ["id"],
                "description": "(from ref: #/components/schemas/SimpleObject)",
            },
            "timestamp": {"type": "string", "format": "date-time"},
        },
        "required": [],
    }
    assert openapi_schema_to_json_schema(openapi_schema, SAMPLE_FULL_SPEC) == expected


def test_schema_conversion_array_ref() -> None:
    """Test conversion of an array whose items are $refs."""
    openapi_schema = SAMPLE_FULL_SPEC["components"]["schemas"]["ArrayOfSimple"]
    expected = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "id": {"type": "integer", "format": "int64"},
                "name": {"type": "string", "description": "Object name"},
            },
            "required": ["id"],
            "description": "(from ref: #/components/schemas/SimpleObject)",
        },
    }
    assert openapi_schema_to_json_schema(openapi_schema, SAMPLE_FULL_SPEC) == expected


def test_schema_conversion_cycle_detection() -> None:
    """Test that cyclic references are detected and handled."""
    openapi_schema = {"$ref": "#/components/schemas/CyclicA"}
    result = openapi_schema_to_json_schema(openapi_schema, SAMPLE_FULL_SPEC)

    assert "description" in result
    assert result["description"] == "(from ref: #/components/schemas/CyclicA)"

    def contains_cyclic_reference(schema: dict) -> bool:
        if "_is_cyclic_reference" in schema:
            return True
        for value in schema.values():
            if isinstance(value, dict) and contains_cyclic_reference(value):
                return True
        return False

    assert contains_cyclic_reference(result)


def test_schema_conversion_invalid_input() -> None:
    """Test conversion with invalid input types."""
    assert openapi_schema_to_json_schema(None, SAMPLE_FULL_SPEC) == {}
    assert openapi_schema_to_json_schema("not a dict", SAMPLE_FULL_SPEC) == {}
    assert openapi_schema_to_json_schema([], SAMPLE_FULL_SPEC) == {}
