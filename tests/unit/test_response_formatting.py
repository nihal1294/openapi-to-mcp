from mcp import MCPError
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from openapi_to_mcp.adapters.testing.response_formatting import (
    format_mcp_error,
    format_mcp_response,
)


def test_format_mapping_envelope_preserves_opaque_keys() -> None:
    payload = {
        "result": {"_meta": {"source": "mapping"}},
        "_meta": {"envelope": True},
    }

    response = format_mcp_response(payload, req_id=6)

    assert response == {
        "jsonrpc": "2.0",
        "id": 6,
        "result": {"_meta": {"source": "mapping"}},
        "_meta": {"envelope": True},
    }


def test_format_none_returns_internal_error() -> None:
    assert format_mcp_response(None, req_id=13) == {
        "jsonrpc": "2.0",
        "id": 13,
        "error": {
            "code": -32603,
            "message": "Internal error: No response data received from server.",
        },
    }


def test_format_list_tools_result_only_normalizes_model_meta_fields() -> None:
    result = ListToolsResult(
        _meta={"trace": {"_meta": {"source": "server"}}},
        ttlMs=250,
        cacheScope="public",
        tools=[
            Tool(
                name="lookup",
                inputSchema={
                    "type": "object",
                    "_meta": {"source": "schema"},
                },
                _meta={"annotations": {"_meta": {"safe": True}}},
            )
        ],
    )

    response = format_mcp_response(result, req_id=7)

    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 7
    assert response["ttlMs"] == 250
    assert response["cacheScope"] == "public"
    assert response["resultType"] == "complete"
    assert response["meta"] == {"trace": {"_meta": {"source": "server"}}}
    assert response["tools"][0]["inputSchema"] == {
        "type": "object",
        "_meta": {"source": "schema"},
    }
    assert response["tools"][0]["meta"] == {"annotations": {"_meta": {"safe": True}}}


def test_format_call_tool_result_keeps_v2_fields_and_error_alias() -> None:
    result = CallToolResult(
        _meta={"request": {"_meta": {"attempt": 2}}},
        content=[
            TextContent(
                type="text",
                text="failed",
                _meta={"delivery": {"_meta": {"channel": "stdio"}}},
            )
        ],
        structuredContent={
            "status": "rejected",
            "_meta": {"source": "tool"},
        },
        isError=True,
        resultType="input_required",
    )

    response = format_mcp_response(result, req_id=8)

    assert response["isError"] is True
    assert response["structuredContent"] == {
        "status": "rejected",
        "_meta": {"source": "tool"},
    }
    assert response["resultType"] == "input_required"
    assert response["meta"] == {"request": {"_meta": {"attempt": 2}}}
    assert response["content"][0]["meta"] == {
        "delivery": {"_meta": {"channel": "stdio"}}
    }


def test_format_mcp_error_uses_public_v2_properties() -> None:
    error = MCPError(
        -32602,
        "bad input",
        {"field": "status", "_meta": {"source": "validator"}},
    )

    assert format_mcp_error(error, req_id=9) == {
        "jsonrpc": "2.0",
        "id": 9,
        "error": {
            "code": -32602,
            "message": "bad input",
            "data": {
                "field": "status",
                "_meta": {"source": "validator"},
            },
        },
    }
