import logging
from typing import Any

import pytest

from openapi_to_mcp.common.exceptions import MappingError
from openapi_to_mcp.mapping.mapper import Mapper

logger = logging.getLogger(__name__)


SAMPLE_SPEC_MINIMAL: dict[str, Any] = {
    "openapi": "3.0.0",
    "info": {"title": "Minimal API", "version": "1.0"},
    "paths": {},
}

SAMPLE_SPEC: dict[str, Any] = {
    "openapi": "3.0.0",
    "info": {"title": "Mapper Test API", "version": "1.0"},
    "paths": {
        "/users": {
            "get": {
                "summary": "List users",
                "operationId": "listUsers",
                "parameters": [
                    {"name": "limit", "in": "query", "schema": {"type": "integer"}},
                    {
                        "name": "offset",
                        "in": "query",
                        "schema": {"type": "integer", "default": 0},
                    },
                    {
                        "name": "X-Request-ID",
                        "in": "header",
                        "schema": {"type": "string"},
                    },
                ],
                "responses": {"200": {"description": "OK"}},
            },
            "post": {
                "summary": "Create user",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/UserInput"}
                        },
                        "application/xml": {"schema": {"type": "string"}},
                    },
                },
                "responses": {"201": {"description": "Created"}},
            },
        },
        "/users/{userId}": {
            "get": {
                "summary": "Get user by ID",
                "parameters": [
                    {
                        "name": "userId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "format": "uuid"},
                    }
                ],
                "responses": {"200": {"description": "OK"}},
            },
            "delete": {
                "summary": "Delete user",
                "operationId": "delete_user_by_id_explicit",
                "parameters": [{"$ref": "#/components/parameters/UserIdParam"}],
                "responses": {"204": {"description": "No Content"}},
            },
        },
        "/ping": {
            "get": {
                "summary": "Ping endpoint",
                "responses": {"200": {"description": "OK"}},
            }
        },
        "/optionalBody": {
            "put": {
                "summary": "Update with optional body",
                "requestBody": {
                    "required": False,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {"flag": {"type": "boolean"}},
                            }
                        }
                    },
                },
                "responses": {"200": {"description": "OK"}},
            }
        },
        "/formBody": {
            "post": {
                "summary": "Submit form data",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/x-www-form-urlencoded": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "field1": {"type": "string"},
                                    "field2": {"type": "integer"},
                                },
                                "required": ["field1"],
                            }
                        }
                    },
                },
                "responses": {"200": {"description": "OK"}},
            }
        },
    },
    "components": {
        "schemas": {
            "UserInput": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "format": "email"},
                    "name": {"type": "string"},
                },
                "required": ["email"],
            }
        },
        "parameters": {
            "UserIdParam": {
                "name": "userId",
                "in": "path",
                "required": True,
                "schema": {"type": "string", "format": "uuid"},
                "description": "ID of the user",
            }
        },
    },
}


def test_mapper_initialization() -> None:
    """Test successful initialization of the Mapper."""
    mapper = Mapper(spec=SAMPLE_SPEC)
    assert mapper.spec == SAMPLE_SPEC
    assert mapper.mcp_tools == []


def test_mapper_initialization_invalid_spec() -> None:
    """Test initialization failure with invalid spec type."""
    with pytest.raises(MappingError, match="Invalid OpenAPI specification"):
        Mapper(spec="not a dict")


def test_mapper_map_tools_success() -> None:
    """Test the overall map_tools function for successful mapping."""
    mapper = Mapper(spec=SAMPLE_SPEC)
    tools = mapper.map_tools()

    num_tools: int = 7
    assert len(tools) == num_tools

    list_users_tool = next((t for t in tools if t["name"] == "listUsers"), None)
    assert list_users_tool is not None
    assert list_users_tool["description"] == "List users"
    assert list_users_tool["_original_method"] == "GET"
    assert list_users_tool["_original_path"] == "/users"
    assert "inputSchema" in list_users_tool
    assert "limit" in list_users_tool["inputSchema"]["properties"]
    assert "offset" in list_users_tool["inputSchema"]["properties"]
    assert "X-Request-ID" in list_users_tool["inputSchema"]["properties"]
    assert list_users_tool["inputSchema"]["properties"]["limit"]["type"] == "integer"
    assert list_users_tool["inputSchema"]["properties"]["offset"]["type"] == "integer"
    assert (
        list_users_tool["inputSchema"]["properties"]["X-Request-ID"]["type"] == "string"
    )
    assert list_users_tool["inputSchema"]["required"] == []

    get_user_tool = next((t for t in tools if t["name"] == "get_users_by_userId"), None)
    assert get_user_tool is not None
    assert "userId" in get_user_tool["inputSchema"]["properties"]
    assert get_user_tool["inputSchema"]["properties"]["userId"]["type"] == "string"
    assert get_user_tool["inputSchema"]["properties"]["userId"]["format"] == "uuid"
    assert "userId" in get_user_tool["inputSchema"]["required"]
    assert len(get_user_tool["_original_parameters"]) == 1
    assert get_user_tool["_original_parameters"][0]["name"] == "userId"
    assert get_user_tool["_original_parameters"][0]["in"] == "path"
    assert get_user_tool["_original_parameters"][0]["required"] is True

    post_users_tool = next((t for t in tools if t["name"] == "post_users"), None)
    assert post_users_tool is not None
    assert "requestBody" in post_users_tool["inputSchema"]["properties"]
    assert "requestBody" in post_users_tool["inputSchema"]["required"]
    assert (
        post_users_tool["_original_request_body"]["content_type"] == "application/json"
    )

    put_optional_body_tool = next(
        (t for t in tools if t["name"] == "put_optionalBody"), None
    )
    assert put_optional_body_tool is not None
    assert "requestBody" in put_optional_body_tool["inputSchema"]["properties"]
    assert "requestBody" not in put_optional_body_tool["inputSchema"]["required"]
    assert put_optional_body_tool["_original_request_body"]["required"] is False

    post_form_body_tool = next((t for t in tools if t["name"] == "post_formBody"), None)
    assert post_form_body_tool is not None
    assert "requestBody" in post_form_body_tool["inputSchema"]["properties"]
    assert "requestBody" in post_form_body_tool["inputSchema"]["required"]
    form_schema = post_form_body_tool["inputSchema"]["properties"]["requestBody"]
    assert form_schema["type"] == "object"
    assert "field1" in form_schema["properties"]
    assert "field1" in form_schema["required"]
    assert (
        post_form_body_tool["_original_request_body"]["content_type"]
        == "application/x-www-form-urlencoded"
    )


def test_mapper_map_operation_get_simple() -> None:
    """Test mapping a simple GET operation without parameters."""
    mapper = Mapper(spec=SAMPLE_SPEC)
    method = "get"
    path = "/ping"
    operation = SAMPLE_SPEC["paths"]["/ping"]["get"]

    tool = mapper._map_operation_to_tool(method, path, operation)

    assert tool["name"] == "get_ping"
    assert tool["description"] == "Ping endpoint"
    assert tool["inputSchema"] == {"type": "object", "properties": {}, "required": []}
    assert tool["_original_method"] == "GET"
    assert tool["_original_path"] == "/ping"
    assert tool["_original_parameters"] == []
    assert tool["_original_request_body"] is None


def test_mapper_map_operation_with_query_and_header_params() -> None:
    """Test mapping a GET operation with query and header parameters."""
    mapper = Mapper(spec=SAMPLE_SPEC)
    method = "get"
    path = "/users"
    operation = SAMPLE_SPEC["paths"]["/users"]["get"]

    tool = mapper._map_operation_to_tool(method, path, operation)

    assert tool["name"] == "listUsers"
    props = tool["inputSchema"]["properties"]
    assert "limit" in props
    assert props["limit"]["type"] == "integer"
    assert "offset" in props
    assert props["offset"]["type"] == "integer"
    assert "X-Request-ID" in props
    assert props["X-Request-ID"]["type"] == "string"
    assert tool["inputSchema"]["required"] == []
    num_parameters: int = 3
    assert len(tool["_original_parameters"]) == num_parameters
    assert any(
        p["name"] == "limit" and p["in"] == "query"
        for p in tool["_original_parameters"]
    )
    assert any(
        p["name"] == "offset" and p["in"] == "query"
        for p in tool["_original_parameters"]
    )
    assert any(
        p["name"] == "X-Request-ID" and p["in"] == "header"
        for p in tool["_original_parameters"]
    )


def test_mapper_map_operation_with_path_param() -> None:
    """Test mapping a GET operation with a required path parameter."""
    mapper = Mapper(spec=SAMPLE_SPEC)
    method = "get"
    path = "/users/{userId}"
    operation = SAMPLE_SPEC["paths"]["/users/{userId}"]["get"]

    tool = mapper._map_operation_to_tool(method, path, operation)

    assert tool["name"] == "get_users_by_userId"
    props = tool["inputSchema"]["properties"]
    assert "userId" in props
    assert props["userId"]["type"] == "string"
    assert props["userId"]["format"] == "uuid"
    assert "userId" in tool["inputSchema"]["required"]
    assert len(tool["_original_parameters"]) == 1
    param = tool["_original_parameters"][0]
    assert param["name"] == "userId"
    assert param["in"] == "path"
    assert param["required"] is True


def test_mapper_map_operation_with_request_body_json_preference() -> None:
    """Test mapping a POST operation with multiple content types, preferring JSON."""
    mapper = Mapper(spec=SAMPLE_SPEC)
    method = "post"
    path = "/users"
    operation = SAMPLE_SPEC["paths"]["/users"]["post"]

    tool = mapper._map_operation_to_tool(method, path, operation)

    assert tool["name"] == "post_users"
    assert "requestBody" in tool["inputSchema"]["properties"]
    assert "requestBody" in tool["inputSchema"]["required"]
    rb_schema = tool["inputSchema"]["properties"]["requestBody"]
    assert rb_schema["type"] == "object"
    assert "email" in rb_schema["properties"]
    assert "name" in rb_schema["properties"]
    assert "email" in rb_schema["required"]
    assert tool["_original_parameters"] == []
    assert tool["_original_request_body"] is not None
    assert tool["_original_request_body"]["required"] is True
    assert tool["_original_request_body"]["content_type"] == "application/json"


def test_mapper_map_operation_with_request_body_form() -> None:
    """Test mapping a POST operation with form data."""
    mapper = Mapper(spec=SAMPLE_SPEC)
    method = "post"
    path = "/formBody"
    operation = SAMPLE_SPEC["paths"]["/formBody"]["post"]

    tool = mapper._map_operation_to_tool(method, path, operation)

    assert tool["name"] == "post_formBody"
    assert "requestBody" in tool["inputSchema"]["properties"]
    assert "requestBody" in tool["inputSchema"]["required"]
    rb_schema = tool["inputSchema"]["properties"]["requestBody"]
    assert rb_schema["type"] == "object"
    assert "field1" in rb_schema["properties"]
    assert "field2" in rb_schema["properties"]
    assert "field1" in rb_schema["required"]
    assert (
        tool["_original_request_body"]["content_type"]
        == "application/x-www-form-urlencoded"
    )


def test_mapper_map_operation_with_optional_request_body() -> None:
    """Test mapping a PUT operation with an optional request body."""
    mapper = Mapper(spec=SAMPLE_SPEC)
    method = "put"
    path = "/optionalBody"
    operation = SAMPLE_SPEC["paths"]["/optionalBody"]["put"]

    tool = mapper._map_operation_to_tool(method, path, operation)

    assert tool["name"] == "put_optionalBody"
    assert "requestBody" in tool["inputSchema"]["properties"]
    assert "requestBody" not in tool["inputSchema"]["required"]
    rb_schema = tool["inputSchema"]["properties"]["requestBody"]
    assert rb_schema["type"] == "object"
    assert "flag" in rb_schema["properties"]
    assert tool["_original_request_body"]["required"] is False


def test_mapper_map_operation_with_ref_parameter() -> None:
    """Test mapping an operation that uses a $ref for a parameter."""
    mapper = Mapper(spec=SAMPLE_SPEC)
    method = "delete"
    path = "/users/{userId}"
    operation = SAMPLE_SPEC["paths"]["/users/{userId}"]["delete"]

    tool = mapper._map_operation_to_tool(method, path, operation)

    assert tool["name"] == "delete_user_by_id_explicit"
    props = tool["inputSchema"]["properties"]
    assert "userId" in props
    assert props["userId"]["type"] == "string"
    assert props["userId"]["format"] == "uuid"
    assert "ID of the user" in props["userId"]["description"]
    assert "userId" in tool["inputSchema"]["required"]
    assert len(tool["_original_parameters"]) == 1
    param = tool["_original_parameters"][0]
    assert param["name"] == "userId"
    assert param["in"] == "path"
    assert param["required"] is True


def test_mapper_skips_invalid_operations() -> None:
    """Test that invalid entries under paths are skipped."""
    invalid_spec = {
        "openapi": "3.0.0",
        "info": {"title": "Invalid", "version": "1.0"},
        "paths": {
            "/good": {"get": {"summary": "Good one", "responses": {"200": {}}}},
            "/bad1": "not an object",
            "/bad2": {"invalid-method": {"summary": "Bad method"}},
            "/bad3": {"get": "not an operation object"},
            "/bad4": {"get": {"parameters": "not a list"}},
        },
    }
    mapper = Mapper(spec=invalid_spec)
    tools = mapper.map_tools()
    assert len(tools) == 2

    good_tool = next((t for t in tools if t["_original_path"] == "/good"), None)
    assert good_tool is not None
    assert good_tool["name"] == "get_good"

    bad4_tool = next((t for t in tools if t["_original_path"] == "/bad4"), None)
    assert bad4_tool is not None
    assert bad4_tool["_original_parameters"] == []


def test_mapper_handles_invalid_paths_object() -> None:
    """Test that an invalid 'paths' object raises an error."""
    invalid_spec = {
        "openapi": "3.0.0",
        "info": {"title": "Invalid Paths", "version": "1.0"},
        "paths": "this should be a dictionary",
    }
    mapper = Mapper(spec=invalid_spec)
    with pytest.raises(MappingError, match="Invalid 'paths' object"):
        mapper.map_tools()


def test_mapper_handles_empty_spec() -> None:
    """Test mapping with an empty but valid spec."""
    mapper = Mapper(spec=SAMPLE_SPEC_MINIMAL)
    tools = mapper.map_tools()
    assert tools == []
