from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner, Result

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
    _, kwargs = mock_execute_mcp_server.call_args
    assert kwargs["transport"] == "streamable-http"
    assert kwargs["method"] == "list"
    assert kwargs["req_id"] == 1
    assert kwargs["endpoint_url"] == "http://localhost:8080/mcp"
    assert kwargs["server_cmd"] is None
    assert kwargs["env"] is None
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
    _, kwargs = mock_execute_mcp_server.call_args
    assert kwargs["transport"] == "stdio"
    assert kwargs["method"] == "call"
    assert kwargs["params"]["tool_name"] == "getUser"
    assert kwargs["params"]["tool_arguments"] == {"id": 42}
    assert kwargs["server_cmd"] == "node ./build/index.js"
    assert kwargs["endpoint_url"] is None
    assert kwargs["env"] == {"TARGET_API_BASE_URL": "http://example.com"}


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


def test_test_server_bad_tool_args_json(
    runner: CliRunner,
    mock_execute_mcp_server: MagicMock,
) -> None:
    result = runner.invoke(
        cli,
        [
            "test-server",
            "--transport",
            "streamable-http",
            "--tool-name",
            "tool",
            "--tool-args",
            "{bad-json",
        ],
    )

    assert result.exit_code != 0
    assert "Tool arguments must be a valid JSON object" in result.output
    mock_execute_mcp_server.assert_not_called()
