from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from pytest_mock import MockerFixture


def _normalize_output(text: str) -> str:
    return " ".join(re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text).split())


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_execute_mcp_server(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("openapi_to_mcp.commands.test_server.execute_mcp_server")


def test_test_server_tool_name_without_args_sends_empty_args(
    runner: CliRunner, mock_execute_mcp_server: MagicMock
) -> None:
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
            "streamable-http",
            "--tool-name",
            "tool",
        ],
    )

    assert result.exit_code == 0
    _, kwargs = mock_execute_mcp_server.call_args
    assert kwargs["params"]["tool_arguments"] == {}


def test_test_server_rejects_non_object_tool_args_json(
    runner: CliRunner, mock_execute_mcp_server: MagicMock
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
            "[]",
        ],
    )

    assert result.exit_code != 0
    assert "Tool arguments must be a valid JSON object" in _normalize_output(
        result.output
    )
    mock_execute_mcp_server.assert_not_called()


def test_test_server_unexpected_error_reports_cleanly(
    runner: CliRunner, mock_execute_mcp_server: MagicMock
) -> None:
    mock_execute_mcp_server.side_effect = RuntimeError("boom")

    result = runner.invoke(
        cli,
        [
            "test-server",
            "--transport",
            "streamable-http",
            "--list-tools",
        ],
    )

    assert result.exit_code != 0
    assert "Unexpected error during testing: boom" in _normalize_output(result.output)
    assert "Traceback" not in result.output
