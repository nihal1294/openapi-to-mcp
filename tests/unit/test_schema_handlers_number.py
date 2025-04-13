from unittest.mock import MagicMock

from openapi_to_mcp.schema.handlers.base import SchemaConverterProtocol
from openapi_to_mcp.schema.handlers.number_schema import NumberSchemaHandler


def test_can_handle_integer() -> None:
    """Test can_handle with integer types."""
    converter_mock = MagicMock(spec=SchemaConverterProtocol)
    handler = NumberSchemaHandler(converter_mock)

    assert handler.can_handle({"type": "integer"})
    assert handler.can_handle({"type": "integer", "format": "int32"})
    assert handler.can_handle({"type": "integer", "format": "int64"})


def test_can_handle_number() -> None:
    """Test can_handle with number types."""
    converter_mock = MagicMock(spec=SchemaConverterProtocol)
    handler = NumberSchemaHandler(converter_mock)

    assert handler.can_handle({"type": "number"})
    assert handler.can_handle({"type": "number", "format": "float"})
    assert handler.can_handle({"type": "number", "format": "double"})


def test_can_handle_rejects_non_numeric() -> None:
    """Test can_handle rejects non-numeric types."""
    converter_mock = MagicMock(spec=SchemaConverterProtocol)
    handler = NumberSchemaHandler(converter_mock)

    assert not handler.can_handle({"type": "string"})
    assert not handler.can_handle({"type": "array"})
    assert not handler.can_handle({"type": "object"})
    assert not handler.can_handle({})
    assert not handler.can_handle({"format": "int32"})
    assert not handler.can_handle("not a dict")


def test_handle_basic_number_type() -> None:
    """Test handling of basic number type with no additional properties."""
    converter_mock = MagicMock(spec=SchemaConverterProtocol)
    handler = NumberSchemaHandler(converter_mock)

    openapi_schema = {"type": "number"}
    json_schema = {}

    handler.handle(openapi_schema, json_schema)

    assert json_schema["type"] == "number"
    assert len(json_schema) == 1


def test_handle_format() -> None:
    """Test handling of format property."""
    converter_mock = MagicMock(spec=SchemaConverterProtocol)
    handler = NumberSchemaHandler(converter_mock)

    openapi_schema = {"type": "integer", "format": "int64"}
    json_schema = {}

    handler.handle(openapi_schema, json_schema)

    assert json_schema["type"] == "integer"
    assert json_schema["format"] == "int64"

    openapi_schema = {"type": "number", "format": "double"}
    json_schema = {}

    handler.handle(openapi_schema, json_schema)

    assert json_schema["type"] == "number"
    assert json_schema["format"] == "double"


def test_handle_constraints() -> None:
    """Test handling of numeric constraints (minimum, maximum, multipleOf)."""
    converter_mock = MagicMock(spec=SchemaConverterProtocol)
    handler = NumberSchemaHandler(converter_mock)

    openapi_schema = {"type": "integer", "minimum": 0, "maximum": 100, "multipleOf": 5}
    json_schema = {}

    handler.handle(openapi_schema, json_schema)

    assert json_schema["type"] == "integer"
    assert json_schema["minimum"] == 0
    assert json_schema["maximum"] == 100
    assert json_schema["multipleOf"] == 5


def test_handle_exclusive_constraints_boolean() -> None:
    """Test handling of boolean exclusiveMinimum/Maximum with minimum/maximum values."""
    converter_mock = MagicMock(spec=SchemaConverterProtocol)
    handler = NumberSchemaHandler(converter_mock)

    openapi_schema = {
        "type": "number",
        "minimum": 0,
        "exclusiveMinimum": True,
        "maximum": 100,
        "exclusiveMaximum": False,
    }
    json_schema = {}

    handler.handle(openapi_schema, json_schema)

    assert json_schema["type"] == "number"
    assert json_schema["exclusiveMinimum"] == 0
    assert json_schema["maximum"] == 100
    assert "exclusiveMaximum" not in json_schema

    openapi_schema = {
        "type": "number",
        "minimum": 0,
        "exclusiveMinimum": False,
        "maximum": 100,
        "exclusiveMaximum": True,
    }
    json_schema = {}

    handler.handle(openapi_schema, json_schema)

    assert json_schema["type"] == "number"
    assert json_schema["minimum"] == 0
    assert "exclusiveMinimum" not in json_schema
    assert json_schema["exclusiveMaximum"] == 100


def test_handle_exclusive_constraints_numeric() -> None:
    """Test handling of numeric exclusiveMinimum/Maximum."""
    converter_mock = MagicMock(spec=SchemaConverterProtocol)
    handler = NumberSchemaHandler(converter_mock)

    openapi_schema = {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 100}
    json_schema = {}

    handler.handle(openapi_schema, json_schema)

    assert json_schema["type"] == "number"
    assert json_schema["exclusiveMinimum"] == 0
    assert json_schema["exclusiveMaximum"] == 100


def test_handle_preserve_existing_type() -> None:
    """Test that handle preserves existing type in json_schema."""
    converter_mock = MagicMock(spec=SchemaConverterProtocol)
    handler = NumberSchemaHandler(converter_mock)

    openapi_schema = {"type": "integer", "minimum": 0}
    json_schema = {"type": "number"}

    handler.handle(openapi_schema, json_schema)

    assert json_schema["type"] == "number"
    assert json_schema["minimum"] == 0


def test_handle_zero_values() -> None:
    """Test handling with zero values for constraints."""
    converter_mock = MagicMock(spec=SchemaConverterProtocol)
    handler = NumberSchemaHandler(converter_mock)

    openapi_schema = {"type": "integer", "minimum": 0, "maximum": 0, "multipleOf": 1}
    json_schema = {}

    handler.handle(openapi_schema, json_schema)

    assert json_schema["minimum"] == 0
    assert json_schema["maximum"] == 0
    assert json_schema["multipleOf"] == 1


def test_handle_negative_values() -> None:
    """Test handling with negative values for constraints."""
    converter_mock = MagicMock(spec=SchemaConverterProtocol)
    handler = NumberSchemaHandler(converter_mock)

    openapi_schema = {
        "type": "integer",
        "minimum": -100,
        "maximum": -1,
        "exclusiveMinimum": -200,
        "exclusiveMaximum": 0,
    }
    json_schema = {}

    handler.handle(openapi_schema, json_schema)

    assert json_schema["minimum"] == -100
    assert json_schema["maximum"] == -1
    assert json_schema["exclusiveMinimum"] == -200
    assert json_schema["exclusiveMaximum"] == 0
