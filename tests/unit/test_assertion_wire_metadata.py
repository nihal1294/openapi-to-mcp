from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from scripts import assert_generated_server_common


def _json_response(
    payload: dict[str, object], headers: dict[str, str] | None = None
) -> MagicMock:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    response.headers = headers or {}
    return response


def test_extract_wire_meta_reads_only_the_mcp_wire_key() -> None:
    response = {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "_meta": {
                "requestId": "request-1",
                "nested": {"_meta": {"source": "server"}},
            },
            "meta": {"requestId": "stale-alias"},
        },
    }

    assert assert_generated_server_common.extract_wire_meta(response) == {
        "requestId": "request-1",
        "nested": {"_meta": {"source": "server"}},
    }


def test_extract_wire_meta_rejects_cli_alias_only_payloads() -> None:
    response = {"result": {"meta": {"requestId": "stale-alias"}}}

    with pytest.raises(AssertionError, match="stale-alias"):
        assert_generated_server_common.extract_wire_meta(response)


def test_streamable_session_adds_optional_identity_headers() -> None:
    session = assert_generated_server_common.StreamableHttpSession(
        "http://localhost:8080/mcp",
        "wire-contract-test",
        identity_header="X-MCP-Tenant",
        identity_value="acme",
    )

    assert session._headers()["X-MCP-Tenant"] == "acme"


def test_streamable_session_call_tool_preserves_raw_wire_response() -> None:
    session = assert_generated_server_common.StreamableHttpSession(
        "http://localhost:8080/mcp", "wire-contract-test"
    )
    wire_response = {
        "jsonrpc": "2.0",
        "id": 7,
        "result": {"_meta": {"requestId": "request-7"}, "content": []},
    }
    with patch(
        "scripts.assert_generated_server_common.requests.post",
        return_value=_json_response(wire_response),
    ) as post:
        response = session.call_tool("echo", {"value": 1}, 7)

    assert response == wire_response
    assert post.call_args.kwargs["json"] == {
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {"name": "echo", "arguments": {"value": 1}},
    }
