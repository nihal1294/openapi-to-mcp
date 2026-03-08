from typing import Any

from openapi_to_mcp.mapping.mapper import Mapper


def test_mapper_ignores_non_dict_path_items_and_bad_parameter_lists() -> None:
    spec: dict[str, Any] = {
        "openapi": "3.0.0",
        "info": {"title": "Loose Paths", "version": "1.0.0"},
        "paths": {
            "/ignored": [],
            "/items": {
                "parameters": "not-a-list",
                "get": {
                    "operationId": "getItems",
                    "responses": {"200": {"description": "OK"}},
                },
            },
        },
    }

    tools = Mapper(spec=spec).map_tools()

    assert [tool["name"] for tool in tools] == ["getItems"]


def test_mapper_ignores_malformed_parameter_entries_and_refs() -> None:
    spec: dict[str, Any] = {
        "openapi": "3.0.0",
        "info": {"title": "Loose Params", "version": "1.0.0"},
        "paths": {
            "/items": {
                "parameters": ["bad", {"$ref": 123}],
                "get": {
                    "operationId": "getItems",
                    "parameters": [
                        {"$ref": "#/components/parameters/BadParam"},
                        {"schema": {"type": "string"}},
                        {
                            "name": "bodyOnly",
                            "in": "body",
                            "schema": {"type": "string"},
                        },
                        {"name": "good", "in": "query", "schema": {"type": "string"}},
                    ],
                    "responses": {"200": {"description": "OK"}},
                },
            }
        },
        "components": {"parameters": {"BadParam": ["oops"]}},
    }

    tool = Mapper(spec=spec).map_tools()[0]

    assert set(tool["inputSchema"]["properties"]) == {"good"}
    assert tool["_original_parameters"] == [
        {
            "name": "good",
            "in": "query",
            "required": False,
            "style": None,
            "explode": None,
            "allow_reserved": None,
        }
    ]


def test_mapper_ignores_invalid_global_security_metadata() -> None:
    spec: dict[str, Any] = {
        "openapi": "3.0.0",
        "info": {"title": "Bad Security", "version": "1.0.0"},
        "security": "not-a-list",
        "components": {"securitySchemes": "not-a-dict"},
        "paths": {
            "/items": {
                "get": {
                    "operationId": "getItems",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }

    tool = Mapper(spec=spec).map_tools()[0]

    assert tool["_original_security"] is None
    assert tool["_original_security_schemes"] == {}


def test_mapper_ignores_components_that_are_not_dicts() -> None:
    spec: dict[str, Any] = {
        "openapi": "3.0.0",
        "info": {"title": "Bad Components", "version": "1.0.0"},
        "security": [{"ApiKeyHeader": []}],
        "components": [],
        "paths": {
            "/items": {
                "get": {
                    "operationId": "getItems",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }

    tool = Mapper(spec=spec).map_tools()[0]

    assert tool["_original_security"] == [{"ApiKeyHeader": []}]
    assert tool["_original_security_schemes"] == {}


def test_mapper_ignores_invalid_request_body_refs_and_content() -> None:
    spec: dict[str, Any] = {
        "openapi": "3.0.0",
        "info": {"title": "Loose Body", "version": "1.0.0"},
        "paths": {
            "/ref": {
                "post": {
                    "operationId": "postRef",
                    "requestBody": {"$ref": "#/components/requestBodies/BadBody"},
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/content": {
                "post": {
                    "operationId": "postContent",
                    "requestBody": {"content": "not-a-dict"},
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
        "components": {"requestBodies": {"BadBody": ["oops"]}},
    }

    tools = {tool["name"]: tool for tool in Mapper(spec=spec).map_tools()}

    assert tools["postRef"]["_original_request_body"] is None
    assert tools["postContent"]["_original_request_body"] is None
