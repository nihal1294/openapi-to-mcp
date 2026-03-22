from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_run_applies_audit_overrides(
    runner: CliRunner, tmp_path: Path, mocker: MockerFixture
) -> None:
    output_dir = tmp_path / "generated"
    subprocess_run = mocker.patch("openapi_to_mcp.commands.run_support.subprocess.run")
    mocker.patch(
        "openapi_to_mcp.commands.run_support.shutil.which", return_value="/usr/bin/tool"
    )
    _mock_generation_output(mocker, output_dir)

    result = runner.invoke(
        cli,
        [
            "run",
            "--openapi-json",
            str(tmp_path / "openapi.yaml"),
            "--output-dir",
            str(output_dir),
            "--audit-mode",
            "logs",
            "--audit-redact-headers",
            "Authorization,X-Trace-Id",
            "--audit-redact-query-params",
            "status,token",
            "--audit-redact-cookie-names",
            "session_token",
            "--audit-redact-request-body-paths",
            "credentials.token",
            "--audit-redact-response-body-paths",
            "echoed.credentials.token",
        ],
    )

    assert result.exit_code == 0
    env_contents = (output_dir / ".env").read_text(encoding="utf-8")
    assert "MCP_AUDIT_MODE=logs" in env_contents
    assert "MCP_AUDIT_REDACT_HEADERS=Authorization,X-Trace-Id" in env_contents
    assert "MCP_AUDIT_REDACT_QUERY_PARAMS=status,token" in env_contents
    assert "MCP_AUDIT_REDACT_COOKIE_NAMES=session_token" in env_contents
    assert "MCP_AUDIT_REDACT_REQUEST_BODY_PATHS=credentials.token" in env_contents
    assert (
        "MCP_AUDIT_REDACT_RESPONSE_BODY_PATHS=echoed.credentials.token" in env_contents
    )
    assert subprocess_run.call_args_list[0].kwargs["env"]["MCP_AUDIT_MODE"] == "logs"
    assert (
        subprocess_run.call_args_list[0].kwargs["env"]["MCP_AUDIT_REDACT_QUERY_PARAMS"]
        == "status,token"
    )
    assert (
        subprocess_run.call_args_list[0].kwargs["env"]["MCP_AUDIT_REDACT_COOKIE_NAMES"]
        == "session_token"
    )
    assert (
        subprocess_run.call_args_list[0].kwargs["env"][
            "MCP_AUDIT_REDACT_RESPONSE_BODY_PATHS"
        ]
        == "echoed.credentials.token"
    )


def test_run_audit_overrides_beat_env_source(
    runner: CliRunner, tmp_path: Path, mocker: MockerFixture
) -> None:
    output_dir = tmp_path / "generated"
    subprocess_run = mocker.patch("openapi_to_mcp.commands.run_support.subprocess.run")
    mocker.patch(
        "openapi_to_mcp.commands.run_support.shutil.which", return_value="/usr/bin/tool"
    )
    _mock_generation_output(mocker, output_dir)

    result = runner.invoke(
        cli,
        [
            "run",
            "--openapi-json",
            str(tmp_path / "openapi.yaml"),
            "--output-dir",
            str(output_dir),
            "--env-source",
            '{"MCP_AUDIT_MODE":"off"}',
            "--audit-mode",
            "logs",
        ],
    )

    assert result.exit_code == 0
    assert "MCP_AUDIT_MODE=logs" in (output_dir / ".env").read_text(encoding="utf-8")
    assert subprocess_run.call_args_list[0].kwargs["env"]["MCP_AUDIT_MODE"] == "logs"


def _mock_generation_output(mocker: MockerFixture, output_dir: Path) -> None:
    def fake_generate_project(**_: object) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / ".env.example").write_text(
            "TARGET_API_BASE_URL=https://example.com\n", encoding="utf-8"
        )

    mocker.patch(
        "openapi_to_mcp.commands.run.generate_project",
        side_effect=fake_generate_project,
    )
