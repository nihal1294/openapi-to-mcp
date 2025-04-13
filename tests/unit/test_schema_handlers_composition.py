from unittest.mock import MagicMock

from openapi_to_mcp.schema.handlers.base import SchemaConverterProtocol
from openapi_to_mcp.schema.handlers.composition import CompositionHandler


def test_can_handle_with_composition_keywords() -> None:
    """Test the can_handle method with various composition keywords."""
    converter_mock = MagicMock(spec=SchemaConverterProtocol)
    handler = CompositionHandler(converter_mock)

    assert handler.can_handle({"allOf": []})
    assert handler.can_handle({"anyOf": []})
    assert handler.can_handle({"oneOf": []})
    assert handler.can_handle({"not": {}})

    assert handler.can_handle({"allOf": [], "anyOf": []})

    assert handler.can_handle({"allOf": [], "title": "Test Schema"})


def test_can_handle_without_composition_keywords() -> None:
    """Test the can_handle method with schemas that don't contain composition keywords."""
    converter_mock = MagicMock(spec=SchemaConverterProtocol)
    handler = CompositionHandler(converter_mock)

    assert not handler.can_handle({"type": "object"})
    assert not handler.can_handle({"properties": {}})
    assert not handler.can_handle({})


def test_can_handle_with_non_dict_input() -> None:
    """Test the can_handle method with non-dict inputs."""
    converter_mock = MagicMock(spec=SchemaConverterProtocol)
    handler = CompositionHandler(converter_mock)

    assert not handler.can_handle([])
    assert not handler.can_handle("not a dict")
    assert not handler.can_handle(None)


def test_handle_allof() -> None:
    """Test handling allOf keyword."""
    converter_mock = MagicMock(spec=SchemaConverterProtocol)
    converter_mock.convert.side_effect = lambda s: {"converted": True, "original": s}
    handler = CompositionHandler(converter_mock)

    openapi_schema = {"allOf": [{"type": "object"}, {"required": ["name"]}]}
    json_schema = {}

    handler.handle(openapi_schema, json_schema)

    assert "allOf" in json_schema
    assert len(json_schema["allOf"]) == 2
    assert all(item["converted"] for item in json_schema["allOf"])
    assert json_schema["allOf"][0]["original"] == {"type": "object"}
    assert json_schema["allOf"][1]["original"] == {"required": ["name"]}


def test_handle_not() -> None:
    """Test handling not keyword."""
    converter_mock = MagicMock(spec=SchemaConverterProtocol)
    converter_mock.convert.return_value = {"converted": True, "type": "null"}
    handler = CompositionHandler(converter_mock)

    openapi_schema = {"not": {"type": "null"}}
    json_schema = {}

    handler.handle(openapi_schema, json_schema)

    assert "not" in json_schema
    assert json_schema["not"]["converted"] is True
    assert json_schema["not"]["type"] == "null"
    converter_mock.convert.assert_called_once_with({"type": "null"})


def test_handle_oneof_and_anyof() -> None:
    """Test handling oneOf and anyOf keywords."""
    converter_mock = MagicMock(spec=SchemaConverterProtocol)
    converter_mock.convert.side_effect = lambda s: {"converted": s["type"]}
    handler = CompositionHandler(converter_mock)

    openapi_schema = {
        "oneOf": [{"type": "string"}, {"type": "number"}],
        "anyOf": [{"type": "object"}, {"type": "array"}],
    }
    json_schema = {}

    handler.handle(openapi_schema, json_schema)

    assert "oneOf" in json_schema
    assert len(json_schema["oneOf"]) == 2
    assert json_schema["oneOf"][0]["converted"] == "string"
    assert json_schema["oneOf"][1]["converted"] == "number"

    assert "anyOf" in json_schema
    assert len(json_schema["anyOf"]) == 2
    assert json_schema["anyOf"][0]["converted"] == "object"
    assert json_schema["anyOf"][1]["converted"] == "array"


def test_handle_with_invalid_types() -> None:
    """Test handling composition keywords with invalid types."""
    converter_mock = MagicMock(spec=SchemaConverterProtocol)
    handler = CompositionHandler(converter_mock)

    openapi_schema = {"not": "invalid"}
    json_schema = {}

    handler.handle(openapi_schema, json_schema)
    assert "not" not in json_schema
    converter_mock.convert.assert_not_called()

    converter_mock.reset_mock()

    openapi_schema = {"oneOf": {"not": "a list"}}
    json_schema = {}

    handler.handle(openapi_schema, json_schema)
    assert "oneOf" not in json_schema
    converter_mock.convert.assert_not_called()


def test_handle_with_empty_arrays() -> None:
    """Test handling composition keywords with empty arrays."""
    converter_mock = MagicMock(spec=SchemaConverterProtocol)
    handler = CompositionHandler(converter_mock)

    openapi_schema = {"allOf": [], "anyOf": [], "oneOf": []}
    json_schema = {}

    handler.handle(openapi_schema, json_schema)

    assert "allOf" not in json_schema
    assert "anyOf" not in json_schema
    assert "oneOf" not in json_schema
    converter_mock.convert.assert_not_called()


def test_handle_with_non_dict_items() -> None:
    """Test handling composition keywords with arrays containing non-dict items."""
    converter_mock = MagicMock(spec=SchemaConverterProtocol)
    handler = CompositionHandler(converter_mock)

    openapi_schema = {
        "allOf": [{"type": "object"}, "not a dict", {"type": "string"}, None]
    }
    json_schema = {}

    handler.handle(openapi_schema, json_schema)

    assert "allOf" in json_schema
    assert len(json_schema["allOf"]) == 2
    assert converter_mock.convert.call_count == 2
