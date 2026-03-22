import pytest

from openapi_to_mcp.common.exceptions import GenerationError
from openapi_to_mcp.common.tool_runtime import (
    build_public_tools,
    build_runtime_tool_registry,
    derive_auth_env_vars,
)


def test_build_public_tools_strips_underscore_fields() -> None:
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


def test_build_runtime_tool_registry_renames_all_runtime_fields() -> None:
    tools = [
        {
            "name": "getThing",
            "_original_method": "GET",
            "_original_path": "/things/{thingId}",
            "_original_parameters": [{"name": "thingId", "in": "path"}],
            "_original_request_body": {
                "required": True,
                "content_type": "application/json",
            },
            "_original_security": [{"BearerAuth": []}],
            "_original_security_schemes": {
                "BearerAuth": {"type": "http", "scheme": "bearer"}
            },
            "_policy_execution": {
                "maxConcurrency": 4,
                "timeoutMs": 9000,
                "cacheTtlMs": 60000,
                "rateLimitPerMinute": 30,
                "retryMaxRetries": 2,
                "retryBudgetPerMinute": 15,
                "circuitBreakerFailureThreshold": 3,
                "circuitBreakerCooldownMs": 20000,
            },
        }
    ]

    assert build_runtime_tool_registry(tools) == {
        "getThing": {
            "method": "GET",
            "path": "/things/{thingId}",
            "parameters": [{"name": "thingId", "in": "path"}],
            "requestBody": {"required": True, "content_type": "application/json"},
            "security": [{"BearerAuth": []}],
            "securitySchemes": {"BearerAuth": {"type": "http", "scheme": "bearer"}},
            "execution": {
                "maxConcurrency": 4,
                "timeoutMs": 9000,
                "cacheTtlMs": 60000,
                "rateLimitPerMinute": 30,
                "retryMaxRetries": 2,
                "retryBudgetPerMinute": 15,
                "circuitBreakerFailureThreshold": 3,
                "circuitBreakerCooldownMs": 20000,
            },
        }
    }


def test_build_runtime_tool_registry_requires_tool_name() -> None:
    with pytest.raises(GenerationError, match="missing a valid 'name'"):
        build_runtime_tool_registry([{"_original_method": "GET"}])


def test_derive_auth_env_vars_reads_runtime_registry_security() -> None:
    runtime_tools = {
        "secureThing": {
            "securitySchemes": {
                "Header Key": {"type": "apiKey"},
                "BearerAuth": {"type": "http", "scheme": "bearer"},
                "OAuth2Auth": {"type": "oauth2"},
                "OidcAuth": {"type": "openidconnect"},
            }
        }
    }

    assert derive_auth_env_vars(runtime_tools) == [
        "AUTH_BEARERAUTH_TOKEN",
        "AUTH_HEADER_KEY_API_KEY",
        "AUTH_OAUTH2AUTH_TOKEN",
        "AUTH_OIDCAUTH_TOKEN",
    ]


def test_derive_auth_env_vars_ignores_malformed_scheme_metadata() -> None:
    runtime_tools = {
        "badMap": {"securitySchemes": []},
        "mixed": {
            "securitySchemes": {
                123: {"type": "apiKey"},
                "Good Auth": {"type": "apiKey"},
                "!!!": {"type": "apiKey"},
                "Broken": "nope",
            }
        },
    }

    assert derive_auth_env_vars(runtime_tools) == ["AUTH_GOOD_AUTH_API_KEY"]
