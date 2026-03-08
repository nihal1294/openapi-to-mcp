from openapi_to_mcp.common.tool_runtime import (
    build_public_tools,
    build_runtime_tool_registry,
    derive_auth_env_vars,
)


def test_build_public_tools_strips_internal_runtime_fields() -> None:
    tools = [
        {
            "name": "getThing",
            "description": "Fetch thing",
            "inputSchema": {"type": "object"},
            "_original_method": "GET",
            "_original_path": "/things/{thingId}",
        }
    ]

    assert build_public_tools(tools) == [
        {
            "name": "getThing",
            "description": "Fetch thing",
            "inputSchema": {"type": "object"},
        }
    ]

    assert build_runtime_tool_registry(tools) == {
        "getThing": {
            "method": "GET",
            "path": "/things/{thingId}",
        }
    }


def test_derive_auth_env_vars_reads_runtime_registry_security() -> None:
    runtime_tools = {
        "secureThing": {
            "securitySchemes": {
                "Header Key": {"type": "apiKey"},
                "BearerAuth": {"type": "http", "scheme": "bearer"},
            }
        }
    }

    assert derive_auth_env_vars(runtime_tools) == [
        "AUTH_BEARERAUTH_TOKEN",
        "AUTH_HEADER_KEY_API_KEY",
    ]
