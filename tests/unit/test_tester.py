import subprocess
from unittest.mock import MagicMock

import pytest

from openapi_to_mcp.adapters.testing.server_tester import (
    ServerConnectionError as McpTestError,
)
from openapi_to_mcp.adapters.testing.server_tester import (
    SseTransport,
    StdioTransport,
    _create_transport_strategy,
    _format_response,
    execute_mcp_server,
)


def test_mcp_test_error_instantiation() -> None:
    """Test that McpTestError can be instantiated."""
    error_msg = "This is a test error"
    try:
        raise McpTestError(error_msg)
    except McpTestError as e:
        assert str(e) == error_msg


@pytest.fixture
def mock_requests_post(mocker: MagicMock) -> MagicMock:
    """Fixture to mock requests.post."""
    return mocker.patch("openapi_to_mcp.adapters.testing.server_tester.requests.post")


def test_sse_transport_initialization() -> None:
    """Test successful initialization of SseTransport."""
    sse_url = "http://test.com"
    transport = SseTransport(sse_url)
    assert transport.sse_url == f"{sse_url}/sse"


def test_sse_transport_initialization_error() -> None:
    """Test initialization failure with empty URL."""
    with pytest.raises(ValueError, match="sse_url is required for SSE transport"):
        SseTransport("")


def test_stdio_transport_initialization() -> None:
    """Test successful initialization of StdioTransport."""
    server_cmd = "server start"
    env = {"TEST_ENV": "value"}
    transport = StdioTransport(server_cmd, env)
    assert transport.server_cmd == server_cmd
    assert transport.env == env


def test_stdio_transport_initialization_error() -> None:
    """Test initialization failure with empty command."""
    with pytest.raises(ValueError, match="server_cmd is required for stdio transport"):
        StdioTransport("")


def test_create_transport_strategy_stdio() -> None:
    """Test creating a stdio transport strategy."""
    server_cmd = "server start"
    env = {"TEST_ENV": "value"}
    strategy = _create_transport_strategy("stdio", server_cmd=server_cmd, env=env)
    assert isinstance(strategy, StdioTransport)
    assert strategy.server_cmd == server_cmd
    assert strategy.env == env


def test_create_transport_strategy_sse() -> None:
    """Test creating an SSE transport strategy."""
    sse_url = "http://test.com"
    strategy = _create_transport_strategy("sse", sse_url=sse_url)
    assert isinstance(strategy, SseTransport)
    assert strategy.sse_url == f"{sse_url}/sse"


def test_create_transport_strategy_stdio_missing_cmd() -> None:
    """Test error when creating stdio transport without command."""
    with pytest.raises(ValueError, match="server_cmd is required for stdio transport"):
        _create_transport_strategy("stdio")


def test_create_transport_strategy_sse_missing_url() -> None:
    """Test error when creating SSE transport without URL."""
    with pytest.raises(ValueError, match="sse_url is required for sse transport"):
        _create_transport_strategy("sse")


def test_create_transport_strategy_invalid_type() -> None:
    """Test error with invalid transport type."""
    with pytest.raises(ValueError, match="Unsupported transport type: invalid"):
        _create_transport_strategy("invalid")


def test_format_response_success() -> None:
    """Test formatting a successful response."""
    response = MagicMock()
    response.model_dump.return_value = {"result": "success"}
    req_id = 5

    result = _format_response(response, req_id)

    assert result["jsonrpc"] == "2.0"
    assert result["id"] == req_id
    assert result["result"] == "success"


def test_format_response_none() -> None:
    """Test formatting a None response."""
    req_id = 5

    result = _format_response(None, req_id)

    assert result["jsonrpc"] == "2.0"
    assert result["id"] == req_id
    assert "error" in result


@pytest.fixture
def mock_subprocess_popen(mocker: MagicMock) -> MagicMock:
    """Fixture to mock subprocess.Popen."""
    mock_proc = MagicMock(spec=subprocess.Popen)
    mock_proc.communicate.return_value = ('{"result": "stdio success", "id": 1}\n', "")
    mock_proc.returncode = 0
    return mocker.patch(
        "openapi_to_mcp.adapters.testing.server_tester.subprocess.Popen",
        return_value=mock_proc,
    )


@pytest.fixture
def mock_shlex_split(mocker: MagicMock) -> MagicMock:
    """Fixture to mock shlex.split."""
    return mocker.patch(
        "openapi_to_mcp.adapters.testing.server_tester.shlex.split",
        return_value=["server", "start"],
    )


@pytest.fixture
def mock_time_sleep(mocker: MagicMock) -> MagicMock:
    """Fixture to mock time.sleep."""
    return mocker.patch("openapi_to_mcp.adapters.testing.server_tester.time.sleep")


@pytest.mark.asyncio
async def test_perform_mcp_request_list_tools(mocker: MagicMock) -> None:
    """Test _perform_mcp_request with list method."""
    from mcp import ClientSession, ListToolsResult

    from openapi_to_mcp.adapters.testing.server_tester import _perform_mcp_request

    session_mock = mocker.AsyncMock(spec=ClientSession)
    result_mock = mocker.MagicMock(spec=ListToolsResult)
    session_mock.list_tools.return_value = result_mock

    result = await _perform_mcp_request(session_mock, "list", None)

    session_mock.list_tools.assert_called_once()
    assert result is result_mock


@pytest.mark.asyncio
async def test_perform_mcp_request_call(mocker: MagicMock) -> None:
    """Test _perform_mcp_request with call method."""
    from mcp import ClientSession
    from mcp.types import CallToolResult

    from openapi_to_mcp.adapters.testing.server_tester import _perform_mcp_request

    session_mock = mocker.AsyncMock(spec=ClientSession)
    result_mock = mocker.MagicMock(spec=CallToolResult)
    session_mock.call_tool.return_value = result_mock

    tool_name = "test_tool"
    tool_args = {"key": "value"}
    params = {"tool_name": tool_name, "tool_arguments": tool_args}

    result = await _perform_mcp_request(session_mock, "call", params)

    session_mock.call_tool.assert_called_once_with(name=tool_name, arguments=tool_args)
    assert result is result_mock


@pytest.mark.asyncio
async def test_perform_mcp_request_unsupported_method(mocker: MagicMock) -> None:
    """Test _perform_mcp_request with unsupported method."""
    from mcp import ClientSession

    from openapi_to_mcp.adapters.testing.server_tester import (
        UnsupportedMethodError,
        _perform_mcp_request,
    )

    session_mock = mocker.AsyncMock(spec=ClientSession)

    with pytest.raises(UnsupportedMethodError):
        await _perform_mcp_request(session_mock, "invalid", None)


@pytest.mark.asyncio
async def test_execute_mcp_server_integration(mocker: MagicMock) -> None:
    """Test the overall execute_mcp_server function."""
    transport_strategy = mocker.MagicMock()
    transport_strategy.connect_and_execute = mocker.AsyncMock()
    transport_strategy.connect_and_execute.return_value = {"result": "success"}

    mocker.patch(
        "openapi_to_mcp.adapters.testing.server_tester._create_transport_strategy",
        return_value=transport_strategy,
    )

    result = await execute_mcp_server(
        transport="stdio",
        method="list",
        params={"key": "value"},
        req_id=1,
        server_cmd="test command",
    )

    transport_strategy.connect_and_execute.assert_called_once_with(
        "list", {"key": "value"}, 1
    )
    assert result == {"result": "success"}
