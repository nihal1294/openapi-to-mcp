from typing import Any

from jsonschema import Draft202012Validator

from openapi_to_mcp.mapping.mapper import Mapper


def test_mapper_resolves_ref_parameters_before_merging() -> None:
    spec: dict[str, Any] = {
        "openapi": "3.0.0",
        "info": {"title": "Ref Params", "version": "1.0.0"},
        "paths": {
            "/items": {
                "parameters": [{"$ref": "#/components/parameters/LocaleParam"}],
                "get": {
                    "operationId": "getItems",
                    "parameters": [
                        {
                            "name": "locale",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string", "enum": ["en", "fr"]},
                        }
                    ],
                    "responses": {"200": {"description": "OK"}},
                },
            }
        },
        "components": {
            "parameters": {
                "LocaleParam": {
                    "name": "locale",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "string"},
                }
            }
        },
    }

    tool = Mapper(spec=spec).map_tools()[0]

    assert "locale" in tool["inputSchema"]["required"]
    assert tool["_original_parameters"] == [
        {
            "name": "locale",
            "in": "query",
            "required": True,
            "style": None,
            "explode": None,
            "allow_reserved": None,
        }
    ]


def test_mapper_uses_first_non_json_request_body_schema() -> None:
    spec: dict[str, Any] = {
        "openapi": "3.0.0",
        "info": {"title": "Form Body", "version": "1.0.0"},
        "paths": {
            "/submit": {
                "post": {
                    "operationId": "submitForm",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/x-www-form-urlencoded": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"name": {"type": "string"}},
                                    "required": ["name"],
                                }
                            }
                        },
                    },
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }

    tool = Mapper(spec=spec).map_tools()[0]

    assert "requestBody" in tool["inputSchema"]["properties"]
    assert "requestBody" in tool["inputSchema"]["required"]
    assert tool["_original_request_body"] == {
        "required": True,
        "content_type": "application/x-www-form-urlencoded",
    }


def test_mapper_records_required_request_body_without_schema() -> None:
    spec: dict[str, Any] = {
        "openapi": "3.0.0",
        "info": {"title": "Missing Body Schema", "version": "1.0.0"},
        "paths": {
            "/submit": {
                "post": {
                    "operationId": "submitForm",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"example": {"name": "x"}}},
                    },
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }

    tool = Mapper(spec=spec).map_tools()[0]

    assert "requestBody" not in tool["inputSchema"]["properties"]
    assert "requestBody" not in tool["inputSchema"]["required"]
    assert tool["_original_request_body"] == {
        "required": True,
        "content_type": None,
    }


def test_mapper_preserves_required_boolean_request_body_schema() -> None:
    """A false request-body schema remains a required reject-all input."""
    spec: dict[str, Any] = {
        "openapi": "3.1.0",
        "info": {"title": "Boolean Body", "version": "1.0.0"},
        "paths": {
            "/submit": {
                "post": {
                    "operationId": "submit",
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": False}},
                    },
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }

    tool = Mapper(spec=spec).map_tools()[0]
    input_schema = tool["inputSchema"]

    assert input_schema["required"] == ["requestBody"]
    assert input_schema["properties"]["requestBody"] == {"not": {}}
    assert not Draft202012Validator(input_schema).is_valid(
        {"requestBody": {"name": "example"}}
    )
