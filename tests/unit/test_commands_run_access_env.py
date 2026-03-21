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


def test_run_applies_tool_access_overrides(
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
            "--tool-access-mode",
            "allowlist",
            "--tool-access-default",
            "deny",
            "--tool-identity-header",
            "X-MCP-Tenant",
            "--tool-allowlists",
            '{"acme":["testConversionTool"]}',
        ],
    )

    assert result.exit_code == 0
    env_contents = (output_dir / ".env").read_text(encoding="utf-8")
    assert "MCP_TOOL_ACCESS_MODE=allowlist" in env_contents
    assert "MCP_TOOL_ACCESS_DEFAULT=deny" in env_contents
    assert "MCP_TOOL_IDENTITY_HEADER=X-MCP-Tenant" in env_contents
    assert 'MCP_TOOL_ALLOWLISTS={"acme":["testConversionTool"]}' in env_contents
    assert (
        subprocess_run.call_args_list[0].kwargs["env"]["MCP_TOOL_ACCESS_MODE"]
        == "allowlist"
    )
    assert (
        subprocess_run.call_args_list[0].kwargs["env"]["MCP_TOOL_ACCESS_DEFAULT"]
        == "deny"
    )


def test_run_tool_access_overrides_beat_env_source(
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
            '{"MCP_TOOL_ACCESS_DEFAULT":"allow"}',
            "--tool-access-default",
            "deny",
        ],
    )

    assert result.exit_code == 0
    env_contents = (output_dir / ".env").read_text(encoding="utf-8")
    assert "MCP_TOOL_ACCESS_DEFAULT=deny" in env_contents
    assert (
        subprocess_run.call_args_list[0].kwargs["env"]["MCP_TOOL_ACCESS_DEFAULT"]
        == "deny"
    )


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
