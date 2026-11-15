from __future__ import annotations

from typing import Any

import pytest
from jsonschema import Draft202012Validator

from openapi_to_mcp.common.exceptions import SchemaError
from openapi_to_mcp.mapping.mapper import Mapper
from openapi_to_mcp.mapping.output_schema import extract_output_schema


def test_mapper_emits_output_schema_for_vendor_json_media_type() -> None:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Vendor JSON", "version": "1.0.0"},
        "paths": {
            "/items": {
                "get": {
                    "operationId": "listItems",
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/vnd.api+json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {"ok": {"type": "boolean"}},
                                        "required": ["ok"],
                                    }
                                }
                            },
                        }
                    },
                }
            }
        },
    }

    tool = Mapper(spec=spec).map_tools()[0]

    assert tool["outputSchema"]["required"] == ["ok"]


def test_mapper_omits_output_schema_for_2xx_wildcard_response() -> None:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Wildcard", "version": "1.0.0"},
        "paths": {
            "/status": {
                "get": {
                    "operationId": "getStatus",
                    "responses": {
                        "2XX": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {"ok": {"type": "boolean"}},
                                        "required": ["ok"],
                                    }
                                }
                            },
                        }
                    },
                }
            }
        },
    }

    tool = Mapper(spec=spec).map_tools()[0]

    assert "outputSchema" not in tool


def test_extract_output_schema_returns_none_without_success_responses() -> None:
    operation = {"responses": {"400": {"description": "Bad Request"}}}

    assert extract_output_schema(operation, {}, lambda _ref: {}) is None


def test_extract_output_schema_returns_none_for_non_dict_responses() -> None:
    assert extract_output_schema({"responses": []}, {}, lambda _ref: {}) is None


def test_extract_output_schema_ignores_non_dict_response_entries() -> None:
    operation = {"responses": {"200": "not-a-dict"}}

    assert extract_output_schema(operation, {}, lambda _ref: {}) is None


def test_extract_output_schema_ignores_non_dict_ref_resolution() -> None:
    operation = {"responses": {"200": {"$ref": "#/components/responses/Bad"}}}

    assert extract_output_schema(operation, {}, lambda _ref: ["bad"]) is None


def test_extract_output_schema_handles_schema_conversion_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operation: dict[str, Any] = {
        "responses": {
            "200": {
                "description": "OK",
                "content": {"application/json": {"schema": {"type": "object"}}},
            }
        }
    }

    def raise_schema_error(*_args: object, **_kwargs: object) -> dict[str, Any]:
        raise SchemaError("bad schema")

    monkeypatch.setattr(
        "openapi_to_mcp.mapping.output_schema.openapi_schema_to_json_schema",
        raise_schema_error,
    )

    assert extract_output_schema(operation, {}, lambda _ref: {}) is None


def test_extract_output_schema_ignores_media_entries_without_schema() -> None:
    operation = {
        "responses": {
            "200": {
                "description": "OK",
                "content": {"application/json": "not-a-dict"},
            }
        }
    }

    assert extract_output_schema(operation, {}, lambda _ref: {}) is None


def test_success_schemas_cover_all_statuses_and_media() -> None:
    a = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}
    b = {"type": "object", "properties": {"b": {"type": "string"}}, "required": ["b"]}
    response = lambda schema: {"content": {"application/json": {"schema": schema}}}  # noqa: E731
    operation = {"responses": {"201": response(b), "200": response(a)}}
    result = extract_output_schema(operation, {}, lambda _ref: {})
    assert result == {"type": "object", "anyOf": [a, b]}
    validator = Draft202012Validator(result)
    assert validator.is_valid({"a": "ok"})
    assert validator.is_valid({"b": "ok"})
    assert not validator.is_valid({})
    assert extract_output_schema(operation, {}, lambda _ref: {}) == result


def test_success_identical_schemas_preserve_original_shape() -> None:
    schema = {
        "type": "object",
        "required": ["id"],
        "properties": {"id": {"type": "string"}},
    }
    response = {
        "content": {
            "application/json": {"schema": schema},
            "application/vendor+json": {"schema": schema},
        }
    }
    assert (
        extract_output_schema(
            {"responses": {"200": response, "201": response}}, {}, lambda _ref: {}
        )
        == schema
    )


@pytest.mark.parametrize(
    "response",
    [
        {"description": "empty"},
        {"content": {"text/plain": {"schema": {"type": "string"}}}},
        {
            "content": {
                "application/json": {
                    "schema": {"type": "array", "items": {"type": "string"}}
                }
            }
        },
        {"content": {"application/json": {"schema": {"$ref": "#/missing"}}}},
        {
            "content": {
                "application/json": {"schema": {"type": "object", "nullable": True}}
            }
        },
        {
            "content": {
                "application/json": {"schema": {"type": "object"}},
                "text/plain": {"schema": {"type": "string"}},
            }
        },
    ],
)
def test_unsupported_alternate_or_default_omits_schema(
    response: dict[str, Any],
) -> None:
    good = {"content": {"application/json": {"schema": {"type": "object"}}}}
    for code in ("201", "2XX", "default"):
        assert (
            extract_output_schema(
                {"responses": {"200": good, code: response}}, {}, lambda _ref: {}
            )
            is None
        )


def test_swagger_non_json_produces_omits_schema() -> None:
    operation = {
        "produces": ["application/json", "text/plain"],
        "responses": {"200": {"schema": {"type": "object"}}},
    }
    assert extract_output_schema(operation, {}, lambda _ref: {}) is None


def test_composed_object_responses_are_supported() -> None:
    schema = {
        "anyOf": [
            {"type": "object", "required": ["a"]},
            {"type": "object", "required": ["b"]},
        ]
    }
    response = {"content": {"application/json": {"schema": schema}}}
    result = extract_output_schema(
        {"responses": {"200": response}}, {}, lambda _ref: {}
    )
    assert result is not None
    assert len(result["anyOf"]) == 2


def test_nullable_composition_reference_is_omitted() -> None:
    schema = {"$ref": "#/components/schemas/Nullable"}
    target = {"nullable": True, "oneOf": [{"type": "object"}]}
    response = {"content": {"application/json": {"schema": schema}}}
    spec = {"components": {"schemas": {"Nullable": target}}}
    assert (
        extract_output_schema(
            {"responses": {"200": response}}, spec, lambda _ref: target
        )
        is None
    )


def test_no_content_status_omits_even_if_schema_is_declared() -> None:
    response = {"content": {"application/json": {"schema": {"type": "object"}}}}
    assert (
        extract_output_schema(
            {"responses": {"200": response, "204": response}}, {}, lambda _ref: {}
        )
        is None
    )


@pytest.mark.parametrize("code", ["2XX", "2xx", "default"])
def test_wildcard_and_default_can_include_bodyless_success(code: str) -> None:
    response = {"content": {"application/json": {"schema": {"type": "object"}}}}
    assert (
        extract_output_schema({"responses": {code: response}}, {}, lambda _ref: {})
        is None
    )


def test_untyped_composition_does_not_promise_objects() -> None:
    schema = {
        "anyOf": [
            {"properties": {"a": {"type": "string"}}},
            {"properties": {"b": {"type": "string"}}},
        ]
    }
    assert Draft202012Validator(schema).is_valid("hello")
    response = {"content": {"application/json": {"schema": schema}}}
    assert (
        extract_output_schema({"responses": {"200": response}}, {}, lambda _ref: {})
        is None
    )


def test_untyped_nested_properties_do_not_narrow_schema() -> None:
    schema = {
        "type": "object",
        "properties": {"value": {"properties": {"a": {"type": "string"}}}},
    }
    assert Draft202012Validator(schema).is_valid({"value": "hello"})
    response = {"content": {"application/json": {"schema": schema}}}
    assert (
        extract_output_schema({"responses": {"200": response}}, {}, lambda _ref: {})
        is None
    )


def test_media_order_does_not_change_output_schema() -> None:
    content = {
        "application/json": {"schema": {"type": "object", "required": ["a"]}},
        "application/vnd.test+json": {"schema": {"type": "object", "required": ["b"]}},
    }
    first = {"responses": {"200": {"content": content}}}
    second = {"responses": {"200": {"content": dict(reversed(list(content.items())))}}}
    assert extract_output_schema(first, {}, lambda _ref: {}) == extract_output_schema(
        second, {}, lambda _ref: {}
    )
    assert extract_output_schema(first, {}, lambda _ref: {}) is not None


def test_exclusive_branches_with_dropped_constraints_omit_output_schema() -> None:
    schema = {
        "oneOf": [
            {"type": "object", "maxProperties": 1},
            {"type": "object", "minProperties": 2},
        ]
    }
    validator = Draft202012Validator(schema)
    assert validator.is_valid({"a": 1})
    assert validator.is_valid({"a": 1, "b": 2})
    response = {"content": {"application/json": {"schema": schema}}}
    assert (
        extract_output_schema({"responses": {"200": response}}, {}, lambda _ref: {})
        is None
    )


@pytest.mark.parametrize(
    "unsafe",
    [
        {
            "oneOf": [
                {"type": "object", "maxProperties": 1},
                {"type": "object", "minProperties": 2},
            ]
        },
        {"type": "object", "not": {"type": "object", "maxProperties": 1}},
        {
            "type": "object",
            "properties": {"nested": {"not": {"type": "object", "maxProperties": 1}}},
        },
        {
            "type": "object",
            "properties": {"nested": {"$ref": "#/components/schemas/Unsafe"}},
        },
        {
            "type": "object",
            "properties": {
                "nested": {
                    "type": "array",
                    "items": {"oneOf": [{"type": "string"}, {"type": "integer"}]},
                }
            },
        },
    ],
)
def test_exclusive_and_negative_compositions_omit_output_schema(
    unsafe: dict[str, Any],
) -> None:
    target = {"type": "object", "not": {"type": "object", "maxProperties": 1}}
    spec = {"components": {"schemas": {"Unsafe": target}}}
    response = {"content": {"application/json": {"schema": unsafe}}}
    assert (
        extract_output_schema(
            {"responses": {"200": response}}, spec, lambda _ref: target
        )
        is None
    )
