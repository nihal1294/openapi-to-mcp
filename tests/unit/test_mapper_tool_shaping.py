from typing import Any

from openapi_to_mcp.mapping.mapper import Mapper


def test_mapper_shapes_description_and_input_examples() -> None:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Shaping", "version": "1.0.0"},
        "paths": {
            "/inventory/search/{inventoryId}": {
                "post": {
                    "operationId": "searchInventory",
                    "parameters": [
                        {
                            "name": "inventoryId",
                            "in": "path",
                            "required": True,
                            "example": "inv_123",
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "status",
                            "in": "query",
                            "schema": {
                                "type": "string",
                                "enum": ["active", "archived"],
                            },
                        },
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "example": {"query": "wireless", "limit": 5},
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "query": {"type": "string"},
                                        "limit": {"type": "integer", "default": 10},
                                    },
                                },
                            }
                        },
                    },
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }

    tool = Mapper(spec=spec).map_tools()[0]
    input_schema = tool["inputSchema"]

    assert tool["description"] == "Search inventory."
    assert input_schema["properties"]["inventoryId"]["examples"] == ["inv_123"]
    assert input_schema["properties"]["requestBody"]["examples"] == [
        {"query": "wireless", "limit": 5}
    ]
    assert input_schema["examples"] == [
        {
            "inventoryId": "inv_123",
            "status": "active",
            "requestBody": {"query": "wireless", "limit": 5},
        }
    ]


def test_mapper_preserves_explicit_summary_when_present() -> None:
    spec: dict[str, Any] = {
        "openapi": "3.0.0",
        "info": {"title": "Shaping", "version": "1.0.0"},
        "paths": {
            "/inventory": {
                "get": {
                    "operationId": "searchInventory",
                    "summary": "Find inventory records",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }

    tool = Mapper(spec=spec).map_tools()[0]

    assert tool["description"] == "Find inventory records."


def test_mapper_preserves_null_examples_and_resolves_named_refs() -> None:
    spec: dict[str, Any] = {
        "openapi": "3.0.0",
        "info": {"title": "Shaping", "version": "1.0.0"},
        "components": {
            "examples": {
                "SearchBody": {"value": {"query": "wireless", "limit": 5}},
            }
        },
        "paths": {
            "/inventory/search": {
                "post": {
                    "operationId": "searchInventory",
                    "parameters": [
                        {
                            "name": "status",
                            "in": "query",
                            "example": None,
                            "schema": {"type": "string", "nullable": True},
                        },
                        {
                            "name": "scope",
                            "in": "query",
                            "examples": {"default": {"value": "full"}},
                            "schema": {"type": "string"},
                        },
                    ],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "examples": {
                                    "search": {
                                        "$ref": "#/components/examples/SearchBody"
                                    }
                                },
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "query": {"type": "string"},
                                        "limit": {"type": "integer"},
                                    },
                                },
                            }
                        }
                    },
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }

    tool = Mapper(spec=spec).map_tools()[0]
    input_schema = tool["inputSchema"]

    assert input_schema["properties"]["status"]["examples"] == [None]
    assert input_schema["properties"]["scope"]["examples"] == ["full"]
    assert input_schema["properties"]["requestBody"]["examples"] == [
        {"query": "wireless", "limit": 5}
    ]
    assert input_schema["examples"] == [
        {
            "status": None,
            "scope": "full",
            "requestBody": {"query": "wireless", "limit": 5},
        }
    ]
