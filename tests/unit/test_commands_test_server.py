import logging
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner, Result

from openapi_to_mcp.adapters.testing.server_tester import (
    ServerConnectionError as McpTestError,
)
from openapi_to_mcp.cli import cli


@pytest.fixture
def runner() -> CliRunner:
    """Provides a CliRunner instance."""
    return CliRunner()


@pytest.fixture
def mock_execute_mcp_server(mocker: MagicMock) -> MagicMock:
    """Mocks the execute_mcp_server function."""
    return mocker.patch("openapi_to_mcp.commands.test_server.execute_mcp_server")


def test_execute_server_missing_args(
    runner: CliRunner, caplog: pytest.LogCaptureFixture
) -> None:
    """Test command failure when required arguments are missing."""
    result: Result = runner.invoke(cli, ["test-server"])
    assert result.exit_code != 0
    assert "Missing option '--transport'" in result.output

    with caplog.at_level(
        logging.CRITICAL, logger="openapi_to_mcp.commands.test_server"
    ):
        result = runner.invoke(
            cli, ["test-server", "--transport", "stdio", "--list-tools"]
        )
        assert result.exit_code != 0
        assert "--server-cmd is required for stdio transport" in caplog.text

    with caplog.at_level(
        logging.CRITICAL, logger="openapi_to_mcp.commands.test_server"
    ):
        result = runner.invoke(cli, ["test-server", "--transport", "sse"])
        assert result.exit_code != 0
        assert "Either --list-tools or --tool-name must be specified" in caplog.text

    with caplog.at_level(
        logging.CRITICAL, logger="openapi_to_mcp.commands.test_server"
    ):
        result = runner.invoke(
            cli, ["test-server", "--transport", "sse", "--tool-args", "{}"]
        )
        assert result.exit_code != 0
        assert "--tool-args requires --tool-name to be specified" in caplog.text


def test_test_server_sse_list_tools_success(
    runner: CliRunner, mock_execute_mcp_server: MagicMock
) -> None:
    """Test successful ListTools request via SSE."""
    mock_execute_mcp_server.return_value = {
        "result": {"tools": [{"name": "tool1"}]},
        "id": 1,
    }
    result: Result = runner.invoke(
        cli, ["test-server", "--transport", "sse", "--list-tools"]
    )

    assert result.exit_code == 0
    mock_execute_mcp_server.assert_called_once()
    call_args, call_kwargs = mock_execute_mcp_server.call_args
    assert call_kwargs["transport"] == "sse"
    assert call_kwargs["method"] == "list"
    assert call_kwargs["req_id"] == 1
    assert call_kwargs["sse_url"] == "http://localhost:8080"
    assert '"tools":' in result.output
    assert '"name": "tool1"' in result.output


def test_test_server_stdio_list_tools_success(
    runner: CliRunner, mock_execute_mcp_server: MagicMock
) -> None:
    """Test successful ListTools request via Stdio."""
    server_cmd = "node ./server.js"
    mock_execute_mcp_server.return_value = {
        "result": {"tools": [{"name": "stdio_tool"}]},
        "id": 1,
    }
    result: Result = runner.invoke(
        cli,
        [
            "test-server",
            "--transport",
            "stdio",
            "--server-cmd",
            server_cmd,
            "--list-tools",
        ],
    )

    assert result.exit_code == 0
    mock_execute_mcp_server.assert_called_once()
    call_args, call_kwargs = mock_execute_mcp_server.call_args
    assert call_kwargs["transport"] == "stdio"
    assert call_kwargs["method"] == "list"
    assert call_kwargs["req_id"] == 1
    assert call_kwargs["server_cmd"] == server_cmd
    assert call_kwargs["sse_url"] is None
    assert '"tools":' in result.output
    assert '"name": "stdio_tool"' in result.output


def test_test_server_sse_call_tool_success(
    runner: CliRunner, mock_execute_mcp_server: MagicMock
) -> None:
    """Test successful CallTool request via SSE."""
    tool_name = "myTool"
    tool_args_json = '{"arg1": "val1"}'
    tool_args_dict = {"arg1": "val1"}
    mock_execute_mcp_server.return_value = {"result": "tool executed", "id": 1}

    result: Result = runner.invoke(
        cli,
        [
            "test-server",
            "--transport",
            "sse",
            "--port",
            "8080",
            "--tool-name",
            tool_name,
            "--tool-args",
            tool_args_json,
        ],
    )

    assert result.exit_code == 0
    mock_execute_mcp_server.assert_called_once()
    call_args, call_kwargs = mock_execute_mcp_server.call_args
    assert call_kwargs["transport"] == "sse"
    assert call_kwargs["method"] == "call"
    assert call_kwargs["params"]["tool_name"] == tool_name
    assert call_kwargs["params"]["tool_arguments"] == tool_args_dict
    assert call_kwargs["req_id"] == 1
    assert call_kwargs["sse_url"] == "http://localhost:8080"
    assert '"result": "tool executed"' in result.output


def test_test_server_stdio_call_tool_success(
    runner: CliRunner, mock_execute_mcp_server: MagicMock
) -> None:
    """Test successful CallTool request via Stdio."""
    server_cmd = "npm start"
    tool_name = "stdioTool"
    tool_args_json = '{"arg": true}'
    tool_args_dict = {"arg": True}
    mock_execute_mcp_server.return_value = {"result": "stdio tool done", "id": 1}

    result: Result = runner.invoke(
        cli,
        [
            "test-server",
            "--transport",
            "stdio",
            "--server-cmd",
            server_cmd,
            "--tool-name",
            tool_name,
            "--tool-args",
            tool_args_json,
        ],
    )

    assert result.exit_code == 0
    mock_execute_mcp_server.assert_called_once()
    call_args, call_kwargs = mock_execute_mcp_server.call_args
    assert call_kwargs["transport"] == "stdio"
    assert call_kwargs["method"] == "call"
    assert call_kwargs["params"]["tool_name"] == tool_name
    assert call_kwargs["params"]["tool_arguments"] == tool_args_dict
    assert call_kwargs["req_id"] == 1
    assert call_kwargs["server_cmd"] == server_cmd
    assert '"result": "stdio tool done"' in result.output


def test_test_server_call_tool_invalid_json_args(
    runner: CliRunner,
    mock_execute_mcp_server: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test command failure with invalid JSON in --tool-args."""
    caplog.set_level(logging.ERROR)
    result: Result = runner.invoke(
        cli,
        [
            "test-server",
            "--transport",
            "sse",
            "--tool-name",
            "anyTool",
            "--tool-args",
            '{"invalid json',
        ],
    )
    assert result.exit_code != 0
    assert "Invalid JSON in --tool-args" in caplog.text
    mock_execute_mcp_server.assert_not_called()


def test_test_server_mcp_test_error_handling(
    runner: CliRunner,
    mock_execute_mcp_server: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that McpTestError from underlying functions is handled."""
    caplog.set_level(logging.CRITICAL)
    error_message = "Underlying test error"
    mock_execute_mcp_server.side_effect = McpTestError(error_message)

    result: Result = runner.invoke(
        cli, ["test-server", "--transport", "sse", "--list-tools"]
    )

    assert result.exit_code != 0
    assert "Underlying test error" in caplog.text


def test_test_server_unexpected_error_handling(
    runner: CliRunner,
    mock_execute_mcp_server: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that unexpected errors are caught and logged."""
    caplog.set_level(logging.CRITICAL)
    error_message = "Something unexpected broke"
    mock_execute_mcp_server.side_effect = ValueError(error_message)

    result: Result = runner.invoke(
        cli,
        ["test-server", "--transport", "stdio", "--server-cmd", "cmd", "--list-tools"],
    )

    assert result.exit_code != 0
    assert "unexpected error" in caplog.text.lower()
    assert "Something unexpected broke" in caplog.text
