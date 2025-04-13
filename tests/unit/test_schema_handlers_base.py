from typing import Any

import pytest

from openapi_to_mcp.schema.handlers.base import (
    SchemaConverterProtocol,
    SchemaHandler,
)


class MockSchemaConverter:
    """Mock implementation of SchemaConverterProtocol for testing."""

    def __init__(self, full_spec: dict[str, Any] | None = None) -> None:
        self._full_spec = full_spec or {}

    def convert(self, openapi_schema: dict[str, Any]) -> dict[str, Any]:
        """Mock implementation of convert method."""
        return {"converted": True, **openapi_schema}

    @property
    def full_spec(self) -> dict[str, Any]:
        """Mock implementation of full_spec property."""
        return self._full_spec


class ConcreteSchemaHandler(SchemaHandler):
    """Concrete implementation of SchemaHandler for testing."""

    def can_handle(self, schema: dict[str, Any]) -> bool:
        """Test implementation of can_handle."""
        return "test_type" in schema

    def handle(
        self, openapi_schema: dict[str, Any], json_schema: dict[str, Any]
    ) -> None:
        """Test implementation of handle."""
        json_schema["handled"] = True
        json_schema["test_value"] = openapi_schema.get("test_type")


class BrokenSchemaHandler(SchemaHandler):
    """Implementation that doesn't override abstract methods."""


def test_schema_converter_protocol() -> None:
    """Test that our mock implements the SchemaConverterProtocol."""
    converter = MockSchemaConverter()

    schema: SchemaConverterProtocol = converter

    result = schema.convert({"type": "string"})
    assert result["converted"] is True
    assert result["type"] == "string"

    assert schema.full_spec == {}


def test_schema_handler_initialization() -> None:
    """Test SchemaHandler initialization with converter."""
    converter = MockSchemaConverter({"title": "Test API"})
    handler = ConcreteSchemaHandler(converter)

    assert handler.converter is converter
    assert handler.converter.full_spec["title"] == "Test API"


def test_schema_handler_abstract_methods() -> None:
    """Test that SchemaHandler enforces implementation of abstract methods."""
    converter = MockSchemaConverter()

    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        BrokenSchemaHandler(converter)


def test_concrete_schema_handler_can_handle() -> None:
    """Test the can_handle implementation of ConcreteSchemaHandler."""
    converter = MockSchemaConverter()
    handler = ConcreteSchemaHandler(converter)

    assert handler.can_handle({"test_type": "value"}) is True
    assert handler.can_handle({"other_field": "value"}) is False
    assert handler.can_handle({}) is False


def test_concrete_schema_handler_handle() -> None:
    """Test the handle implementation of ConcreteSchemaHandler."""
    converter = MockSchemaConverter()
    handler = ConcreteSchemaHandler(converter)

    openapi_schema = {"test_type": "test_value"}
    json_schema = {}

    handler.handle(openapi_schema, json_schema)

    assert json_schema["handled"] is True
    assert json_schema["test_value"] == "test_value"
