from openapi_to_mcp.mapping.mapper import Mapper


def test_mapper_emits_output_schema_for_openapi_json_object_response() -> None:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Output Schema", "version": "1.0.0"},
        "paths": {
            "/items": {
                "get": {
                    "operationId": "listItems",
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "items": {
                                                "type": "array",
                                                "items": {"type": "string"},
                                            }
                                        },
                                        "required": ["items"],
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
        "properties": {
            "items": {
                "type": "array",
                "items": {"type": "string"},
            }
        },
        "required": ["items"],
    }


def test_mapper_emits_output_schema_for_swagger2_response_schema() -> None:
    spec = {
        "swagger": "2.0",
        "info": {"title": "Swagger Output", "version": "1.0.0"},
        "paths": {
            "/status": {
                "get": {
                    "operationId": "getStatus",
                    "responses": {
                        "200": {
                            "description": "OK",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "ok": {"type": "boolean"},
                                },
                                "required": ["ok"],
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


def test_mapper_emits_output_schema_for_ref_response_object() -> None:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Ref Output", "version": "1.0.0"},
        "paths": {
            "/status": {
                "get": {
                    "operationId": "getStatus",
                    "responses": {
                        "200": {"$ref": "#/components/responses/StatusResponse"}
                    },
                }
            }
        },
        "components": {
            "responses": {
                "StatusResponse": {
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
            }
        },
    }

    tool = Mapper(spec=spec).map_tools()[0]

    assert tool["outputSchema"] == {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
    }


def test_mapper_skips_invalid_response_schema_without_skipping_tool() -> None:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Bad Output", "version": "1.0.0"},
        "paths": {
            "/status": {
                "get": {
                    "operationId": "getStatus",
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Missing"}
                                }
                            },
                        }
                    },
                }
            }
        },
    }

    tools = Mapper(spec=spec).map_tools()

    assert [tool["name"] for tool in tools] == ["getStatus"]
    assert "outputSchema" not in tools[0]


def test_mapper_omits_output_schema_for_array_response() -> None:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Array Output", "version": "1.0.0"},
        "paths": {
            "/items": {
                "get": {
                    "operationId": "listItems",
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"type": "string"},
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


def test_mapper_omits_output_schema_for_mixed_anyof_response() -> None:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Union Output", "version": "1.0.0"},
        "paths": {
            "/status": {
                "get": {
                    "operationId": "getStatus",
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "anyOf": [
                                            {"type": "string"},
                                            {
                                                "type": "object",
                                                "properties": {
                                                    "ok": {"type": "boolean"}
                                                },
                                            },
                                        ]
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
