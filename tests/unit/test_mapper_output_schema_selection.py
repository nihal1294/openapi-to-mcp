from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openapi_to_mcp.common.exceptions import SchemaError
from openapi_to_mcp.mapping.mapper import Mapper
from openapi_to_mcp.mapping.output_schema import extract_output_schema

if TYPE_CHECKING:
    import pytest


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


def test_mapper_emits_output_schema_for_2xx_wildcard_response() -> None:
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

    assert tool["outputSchema"] == {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
    }


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
