from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from openapi_to_mcp.adapters.testing.server_tester import StreamableHttpTransport


def _json_response(payload: object) -> MagicMock:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    response.headers = {}
    return response


def _post_response(
    method: str,
    result_response: dict[str, Any],
) -> dict[str, Any]:
    transport = StreamableHttpTransport("http://localhost:8080/mcp")
    init_response = _json_response(
        {"jsonrpc": "2.0", "id": 1001, "result": {"serverInfo": {}}}
    )
    notification_response = _json_response({})
    params = (
        None
        if method == "list"
        else {"tool_name": "echo", "tool_arguments": {"value": 1}}
    )
    with patch(
        "openapi_to_mcp.adapters.testing.streamable_http_transport.requests.post",
        side_effect=[
            init_response,
            notification_response,
            _json_response(result_response),
        ],
    ):
        return transport._post_jsonrpc(method, params, 1)


def test_streamable_list_normalizes_only_mcp_model_metadata() -> None:
    response = _post_response(
        "list",
        {
            "jsonrpc": "2.0",
            "id": 1,
            "_meta": {"envelope": {"_meta": {"source": "proxy"}}},
            "result": {
                "_meta": {"trace": {"_meta": {"source": "server"}}},
                "tools": [
                    {
                        "name": "echo",
                        "inputSchema": {
                            "type": "object",
                            "_meta": {"source": "schema"},
                        },
                        "_meta": {"tool": {"_meta": {"safe": True}}},
                    }
                ],
            },
        },
    )

    assert response["_meta"] == {"envelope": {"_meta": {"source": "proxy"}}}
    result = response["result"]
    assert result["meta"] == {"trace": {"_meta": {"source": "server"}}}
    assert result["tools"][0]["meta"] == {"tool": {"_meta": {"safe": True}}}
    assert result["tools"][0]["inputSchema"]["_meta"] == {"source": "schema"}


def test_streamable_call_normalizes_only_mcp_model_metadata() -> None:
    response = _post_response(
        "call",
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "_meta": {
                    "requestId": "request-1",
                    "trace": {"_meta": {"source": "server"}},
                },
                "content": [
                    {
                        "type": "text",
                        "text": "ok",
                        "_meta": {"delivery": {"_meta": {"channel": "http"}}},
                    }
                ],
                "structuredContent": {
                    "status": "ok",
                    "_meta": {"source": "tool"},
                },
                "isError": False,
            },
        },
    )

    result = response["result"]
    assert result["meta"] == {
        "requestId": "request-1",
        "trace": {"_meta": {"source": "server"}},
    }
    assert result["content"][0]["meta"] == {"delivery": {"_meta": {"channel": "http"}}}
    assert result["structuredContent"]["_meta"] == {"source": "tool"}


def test_streamable_error_envelope_remains_unchanged() -> None:
    error_response = {
        "jsonrpc": "2.0",
        "id": 1,
        "error": {
            "code": -32602,
            "message": "bad input",
            "data": {"_meta": {"source": "validator"}},
        },
    }

    assert _post_response("call", error_response) == error_response
