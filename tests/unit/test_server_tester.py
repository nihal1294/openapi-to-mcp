from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp import McpError

from openapi_to_mcp.adapters.testing.server_tester import (
    ServerConnectionError,
    SseTransport,
    StdioTransport,
    TransportStrategy,
    _create_transport_strategy,
    _format_response,
    _perform_mcp_request,
    execute_mcp_server,
)


def test_server_connection_error_instantiation() -> None:
    """Test that ServerConnectionError can be instantiated."""
    error_msg = "This is a test error"
    try:
        raise ServerConnectionError(error_msg)
    except ServerConnectionError as e:
        assert str(e) == error_msg


def test_format_response_success() -> None:
    """Test _format_response with valid response data."""
    response_data = MagicMock()
    response_data.model_dump.return_value = {"result": "success"}
    req_id = 123

    result = _format_response(response_data, req_id)

    assert result["result"] == "success"
    assert result["jsonrpc"] == "2.0"
    assert result["id"] == req_id


def test_format_response_none() -> None:
    """Test _format_response with None response data."""
    req_id = 456

    result = _format_response(None, req_id)

    assert "error" in result
    assert result["id"] == req_id
    assert result["jsonrpc"] == "2.0"


def test_create_transport_strategy_stdio() -> None:
    """Test _create_transport_strategy with stdio transport."""
    server_cmd = "test command"
    env = {"TEST_VAR": "value"}

    strategy = _create_transport_strategy("stdio", server_cmd=server_cmd, env=env)

    assert isinstance(strategy, StdioTransport)
    assert strategy.server_cmd == server_cmd
    assert strategy.env == env


def test_create_transport_strategy_stdio_no_cmd() -> None:
    """Test _create_transport_strategy with stdio transport but missing command."""
    with pytest.raises(ValueError, match="server_cmd is required for stdio transport"):
        _create_transport_strategy("stdio")


def test_create_transport_strategy_sse() -> None:
    """Test _create_transport_strategy with sse transport."""
    sse_url = "http://test.com"

    strategy = _create_transport_strategy("sse", sse_url=sse_url)

    assert isinstance(strategy, SseTransport)
    assert strategy.sse_url == f"{sse_url}/sse"


def test_create_transport_strategy_sse_no_url() -> None:
    """Test _create_transport_strategy with sse transport but missing URL."""
    with pytest.raises(ValueError, match="sse_url is required for sse transport"):
        _create_transport_strategy("sse")


def test_create_transport_strategy_invalid() -> None:
    """Test _create_transport_strategy with invalid transport type."""
    with pytest.raises(ValueError, match="Unsupported transport type"):
        _create_transport_strategy("invalid")


@pytest.mark.asyncio
async def test_transport_strategy_base_not_implemented() -> None:
    """Test that the TransportStrategy base class raises NotImplementedError."""
    strategy = TransportStrategy()
    with pytest.raises(
        NotImplementedError, match="Subclasses must implement this method"
    ):
        await strategy.connect_and_execute("list", None, 1)


@pytest.mark.asyncio
async def test_stdio_transport_connection_error() -> None:
    """Test StdioTransport error handling."""
    transport = StdioTransport("test_cmd")
    mock_error = Exception("Connection error")

    with (
        patch("mcp.stdio_client", side_effect=mock_error),
        pytest.raises(ServerConnectionError, match="Failed to connect via stdio"),
    ):
        await transport.connect_and_execute("list", None, 1)


@pytest.mark.asyncio
async def test_sse_transport_connection_error() -> None:
    """Test SseTransport error handling."""
    transport = SseTransport("http://test.com")
    mock_error = Exception("Connection error")

    with (
        patch(
            "openapi_to_mcp.adapters.testing.server_tester.sse_client",
            side_effect=mock_error,
        ),
        pytest.raises(ServerConnectionError, match="Failed to connect via SSE"),
    ):
        await transport.connect_and_execute("list", None, 1)


@pytest.mark.asyncio
async def test_perform_mcp_request_call_missing_tool_name() -> None:
    """Test _perform_mcp_request with 'call' method but missing tool_name in params."""
    session_mock = AsyncMock()

    with pytest.raises(ValueError, match="Missing 'tool_name' in params"):
        await _perform_mcp_request(session_mock, "call", {})

    with pytest.raises(ValueError, match="Missing 'tool_name' in params"):
        await _perform_mcp_request(session_mock, "call", None)


@pytest.mark.asyncio
async def test_execute_mcp_server_invalid_transport() -> None:
    """Test execute_mcp_server with an invalid transport type."""
    with (
        patch(
            "openapi_to_mcp.adapters.testing.server_tester._create_transport_strategy",
            side_effect=ValueError("Invalid transport"),
        ),
        pytest.raises(ValueError, match="Invalid transport"),
    ):
        await execute_mcp_server("invalid", "list")


@pytest.mark.asyncio
async def test_execute_mcp_server_mcp_error() -> None:
    """Test execute_mcp_server with McpError."""
    mock_strategy = MagicMock()
    error_data = MagicMock()
    error_data.message = "Test Error"
    mock_strategy.connect_and_execute.side_effect = McpError(error_data)

    with patch(
        "openapi_to_mcp.adapters.testing.server_tester._create_transport_strategy",
        return_value=mock_strategy,
    ):
        result = await execute_mcp_server("stdio", "list", server_cmd="test")

        assert "error" in result
        assert (
            result["error"]["message"]
            == "MCP Error during stdio test for method 'list': Test Error"
        )
        assert result["jsonrpc"] == "2.0"


@pytest.mark.asyncio
async def test_execute_mcp_server_generic_exception() -> None:
    """Test execute_mcp_server with a generic exception."""
    mock_strategy = MagicMock()
    mock_strategy.connect_and_execute.side_effect = RuntimeError("Unexpected error")

    with (
        patch(
            "openapi_to_mcp.adapters.testing.server_tester._create_transport_strategy",
            return_value=mock_strategy,
        ),
        pytest.raises(RuntimeError, match="Unexpected error"),
    ):
        await execute_mcp_server("stdio", "list", server_cmd="test")


def test_format_response_with_existing_fields() -> None:
    """Test _format_response with response already having jsonrpc and id fields."""
    response_data = MagicMock()
    response_data.model_dump.return_value = {
        "jsonrpc": "2.0",
        "id": 999,
        "result": "success",
    }
    req_id = 123

    result = _format_response(response_data, req_id)

    assert result["jsonrpc"] == "2.0"
    assert result["id"] == 999
    assert result["result"] == "success"


def test_format_response_with_error() -> None:
    """Test _format_response with a response containing an error."""
    response_data = MagicMock()
    response_data.model_dump.return_value = {
        "error": {"code": 100, "message": "Test error"}
    }
    req_id = 123

    result = _format_response(response_data, req_id)

    assert "error" in result
    assert result["error"]["code"] == 100
    assert result["error"]["message"] == "Test error"
