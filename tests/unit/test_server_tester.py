from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp import McpError

from openapi_to_mcp.adapters.testing.server_tester import (
    ServerConnectionError,
    StdioTransport,
    StreamableHttpTransport,
    TransportStrategy,
    _create_transport_strategy,
    _format_response,
    _perform_mcp_request,
    execute_mcp_server,
)


def _json_response(payload: object, headers: dict[str, str] | None = None) -> MagicMock:
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    response.headers = headers or {}
    return response


def test_create_transport_strategy_stdio() -> None:
    strategy = _create_transport_strategy("stdio", server_cmd="node server.js")
    assert isinstance(strategy, StdioTransport)


def test_create_transport_strategy_streamable_http() -> None:
    endpoint_url = "http://localhost:8080/mcp"
    strategy = _create_transport_strategy("streamable-http", endpoint_url=endpoint_url)
    assert isinstance(strategy, StreamableHttpTransport)
    assert strategy.endpoint_url == endpoint_url


def test_create_transport_strategy_missing_required_values() -> None:
    with pytest.raises(ValueError, match="server_cmd is required"):
        _create_transport_strategy("stdio")

    with pytest.raises(ValueError, match="endpoint_url is required"):
        _create_transport_strategy("streamable-http")

    with pytest.raises(ValueError, match="Unsupported transport type"):
        _create_transport_strategy("invalid")


@pytest.mark.asyncio
async def test_transport_strategy_base_not_implemented() -> None:
    strategy = TransportStrategy()
    with pytest.raises(
        NotImplementedError, match="Subclasses must implement this method"
    ):
        await strategy.connect_and_execute("list", None, 1)


def test_format_response_success_and_none() -> None:
    response_data = MagicMock()
    response_data.model_dump.return_value = {"result": "ok"}

    success = _format_response(response_data, req_id=99)
    assert success["jsonrpc"] == "2.0"
    assert success["id"] == 99
    assert success["result"] == "ok"

    failed = _format_response(None, req_id=13)
    assert failed["jsonrpc"] == "2.0"
    assert failed["id"] == 13
    assert "error" in failed


def test_streamable_payload_builder() -> None:
    transport = StreamableHttpTransport("http://localhost:8080/mcp")

    list_payload = transport._build_jsonrpc_payload("list", None, 1)
    assert list_payload == {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {},
    }

    call_payload = transport._build_jsonrpc_payload(
        "call",
        {"tool_name": "echo", "tool_arguments": {"value": 1}},
        2,
    )
    assert call_payload["method"] == "tools/call"
    assert call_payload["params"]["name"] == "echo"
    assert call_payload["params"]["arguments"] == {"value": 1}

    with pytest.raises(ValueError, match="Missing 'tool_name'"):
        transport._build_jsonrpc_payload("call", {}, 3)


def test_streamable_post_jsonrpc_initializes_session() -> None:
    transport = StreamableHttpTransport("http://localhost:8080/mcp")

    init_response = _json_response(
        {"jsonrpc": "2.0", "id": 1001, "result": {"serverInfo": {}}},
        headers={"Mcp-Session-Id": "session-123"},
    )
    initialized_notification_response = _json_response({})
    list_response = _json_response(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"tools": [{"name": "echo"}]},
        }
    )

    with patch(
        "openapi_to_mcp.adapters.testing.server_tester.requests.post",
        side_effect=[init_response, initialized_notification_response, list_response],
    ) as mock_post:
        payload = transport._post_jsonrpc("list", None, 1)

    assert payload["result"]["tools"][0]["name"] == "echo"
    assert mock_post.call_count == 3

    _, init_kwargs = mock_post.call_args_list[0]
    assert init_kwargs["json"]["method"] == "initialize"

    _, notif_kwargs = mock_post.call_args_list[1]
    assert notif_kwargs["json"]["method"] == "notifications/initialized"
    assert notif_kwargs["headers"]["Mcp-Session-Id"] == "session-123"

    _, call_kwargs = mock_post.call_args_list[2]
    assert call_kwargs["json"]["method"] == "tools/list"
    assert call_kwargs["headers"]["Mcp-Session-Id"] == "session-123"


def test_streamable_initialize_error_raises() -> None:
    transport = StreamableHttpTransport("http://localhost:8080/mcp")

    init_error = _json_response(
        {
            "jsonrpc": "2.0",
            "id": 1001,
            "error": {"code": -32600, "message": "init failed"},
        }
    )

    with (
        patch(
            "openapi_to_mcp.adapters.testing.server_tester.requests.post",
            return_value=init_error,
        ),
        pytest.raises(ServerConnectionError, match="Initialize request failed"),
    ):
        transport._post_jsonrpc("list", None, 1)


def test_streamable_parse_json_response_rejects_non_object() -> None:
    transport = StreamableHttpTransport("http://localhost:8080/mcp")
    bad_response = _json_response([{"jsonrpc": "2.0"}])

    with pytest.raises(ServerConnectionError, match="Unexpected non-object JSON"):
        transport._parse_json_response(bad_response)


@pytest.mark.asyncio
async def test_perform_mcp_request_list_and_call() -> None:
    session_mock = AsyncMock()
    list_result = MagicMock()
    call_result = MagicMock()

    session_mock.list_tools.return_value = list_result
    session_mock.call_tool.return_value = call_result

    assert await _perform_mcp_request(session_mock, "list", None) is list_result

    params = {"tool_name": "echo", "tool_arguments": {"x": 1}}
    assert await _perform_mcp_request(session_mock, "call", params) is call_result
    session_mock.call_tool.assert_called_once_with(name="echo", arguments={"x": 1})


@pytest.mark.asyncio
async def test_perform_mcp_request_call_missing_tool_name() -> None:
    session_mock = AsyncMock()

    with pytest.raises(ValueError, match="Missing 'tool_name'"):
        await _perform_mcp_request(session_mock, "call", None)

    with pytest.raises(ValueError, match="Missing 'tool_name'"):
        await _perform_mcp_request(session_mock, "call", {})


@pytest.mark.asyncio
async def test_execute_mcp_server_mcp_error() -> None:
    mock_strategy = MagicMock()
    error_data = MagicMock()
    error_data.message = "boom"
    mock_strategy.connect_and_execute.side_effect = McpError(error_data)

    with patch(
        "openapi_to_mcp.adapters.testing.server_tester._create_transport_strategy",
        return_value=mock_strategy,
    ):
        result = await execute_mcp_server("stdio", "list", server_cmd="node server.js")

    assert result["jsonrpc"] == "2.0"
    assert "error" in result
    assert "boom" in result["error"]["message"]


@pytest.mark.asyncio
async def test_execute_mcp_server_unexpected_error() -> None:
    mock_strategy = MagicMock()
    mock_strategy.connect_and_execute.side_effect = RuntimeError("unexpected")

    with (
        patch(
            "openapi_to_mcp.adapters.testing.server_tester._create_transport_strategy",
            return_value=mock_strategy,
        ),
        pytest.raises(RuntimeError, match="unexpected"),
    ):
        await execute_mcp_server("stdio", "list", server_cmd="node server.js")
