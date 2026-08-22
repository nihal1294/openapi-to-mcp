from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner, Result

from openapi_to_mcp.adapters.testing import ServerTestRequest
from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from unittest.mock import MagicMock


def _normalize_output(text: str) -> str:
    return " ".join(re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text).split())


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_execute_mcp_server(mocker: MagicMock) -> MagicMock:
    return mocker.patch("openapi_to_mcp.commands.test_server.execute_mcp_server")


def test_test_server_requires_transport(runner: CliRunner) -> None:
    result: Result = runner.invoke(cli, ["test-server"])
    assert result.exit_code != 0
    assert "Missing option '--transport'" in _normalize_output(result.output)


def test_test_server_stdio_requires_server_cmd(
    runner: CliRunner,
) -> None:
    result = runner.invoke(
        cli,
        ["test-server", "--transport", "stdio", "--list-tools"],
    )

    assert result.exit_code != 0
    assert "--server-cmd is required for stdio transport" in _normalize_output(
        result.output
    )


def test_test_server_requires_action(
    runner: CliRunner,
) -> None:
    result = runner.invoke(
        cli,
        ["test-server", "--transport", "streamable-http"],
    )

    assert result.exit_code != 0
    assert "Either --list-tools or --tool-name must be specified" in _normalize_output(
        result.output
    )


def test_test_server_tool_args_requires_tool_name(
    runner: CliRunner,
) -> None:
    result = runner.invoke(
        cli,
        [
            "test-server",
            "--transport",
            "streamable-http",
            "--tool-args",
            "{}",
        ],
    )

    assert result.exit_code != 0
    assert "--tool-args requires --tool-name to be specified" in _normalize_output(
        result.output
    )


def test_test_server_streamable_http_list_tools_success(
    runner: CliRunner,
    mock_execute_mcp_server: MagicMock,
) -> None:
    mock_execute_mcp_server.return_value = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"tools": [{"name": "tool1"}]},
    }

    result = runner.invoke(
        cli,
        [
            "test-server",
            "--transport",
            "streamable-http",
            "--host",
            "localhost",
            "--port",
            "8080",
            "--mcp-endpoint",
            "/mcp",
            "--list-tools",
        ],
    )

    assert result.exit_code == 0
    request = mock_execute_mcp_server.call_args.args[0]
    assert isinstance(request, ServerTestRequest)
    assert request.transport == "streamable-http"
    assert request.method == "list"
    assert request.req_id == 1
    assert request.connection.endpoint_url == "http://localhost:8080/mcp"
    assert request.connection.server_cmd is None
    assert request.connection.env is None
    assert '"name": "tool1"' in result.output


def test_test_server_stdio_call_tool_success(
    runner: CliRunner,
    mock_execute_mcp_server: MagicMock,
    mocker: MagicMock,
) -> None:
    parse_env = mocker.patch("openapi_to_mcp.commands.test_server.parse_env_source")
    parse_env.return_value = {"TARGET_API_BASE_URL": "http://example.com"}

    mock_execute_mcp_server.return_value = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"content": [{"type": "text", "text": "ok"}]},
    }

    result = runner.invoke(
        cli,
        [
            "test-server",
            "--transport",
            "stdio",
            "--server-cmd",
            "node ./build/index.js",
            "--tool-name",
            "getUser",
            "--tool-args",
            '{"id": 42}',
            "--env-source",
            "./.env",
        ],
    )

    assert result.exit_code == 0
    parse_env.assert_called_once_with("./.env")
    request = mock_execute_mcp_server.call_args.args[0]
    assert isinstance(request, ServerTestRequest)
    assert request.transport == "stdio"
    assert request.method == "call"
    assert request.params == {
        "tool_name": "getUser",
        "tool_arguments": {"id": 42},
    }
    assert request.connection.server_cmd == "node ./build/index.js"
    assert request.connection.endpoint_url is None
    assert request.connection.env == {"TARGET_API_BASE_URL": "http://example.com"}


def test_test_server_rejects_bad_endpoint(
    runner: CliRunner,
) -> None:
    result = runner.invoke(
        cli,
        [
            "test-server",
            "--transport",
            "streamable-http",
            "--mcp-endpoint",
            "mcp",
            "--list-tools",
        ],
    )

    assert result.exit_code != 0
    assert "--mcp-endpoint must start with '/'" in _normalize_output(result.output)
