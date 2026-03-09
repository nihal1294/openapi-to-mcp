from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from pathlib import Path
    from unittest.mock import MagicMock


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_run_preserves_exported_auth_env_vars(
    runner: CliRunner, tmp_path: Path, mocker: MagicMock
) -> None:
    output_dir = tmp_path / "generated"
    subprocess_run = mocker.patch("openapi_to_mcp.commands.run_support.subprocess.run")
    mocker.patch(
        "openapi_to_mcp.commands.run_support.shutil.which", return_value="/usr/bin/tool"
    )
    mocker.patch.dict(
        "openapi_to_mcp.commands.run_support.os.environ",
        {"AUTH_TEST_API_KEY": "from-shell"},
        clear=False,
    )

    def fake_generate_project(**_: object) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / ".env.example").write_text(
            "TARGET_API_BASE_URL=https://example.com\nAUTH_TEST_API_KEY=\n",
            encoding="utf-8",
        )

    mocker.patch(
        "openapi_to_mcp.commands.run.generate_project",
        side_effect=fake_generate_project,
    )

    result = runner.invoke(
        cli,
        [
            "run",
            "--openapi-json",
            str(tmp_path / "openapi.yaml"),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    assert (
        subprocess_run.call_args_list[0].kwargs["env"]["AUTH_TEST_API_KEY"]
        == "from-shell"
    )


def test_run_applies_runtime_control_overrides(
    runner: CliRunner, tmp_path: Path, mocker: MagicMock
) -> None:
    output_dir = tmp_path / "generated"
    subprocess_run = mocker.patch("openapi_to_mcp.commands.run_support.subprocess.run")
    mocker.patch(
        "openapi_to_mcp.commands.run_support.shutil.which", return_value="/usr/bin/tool"
    )

    def fake_generate_project(**_: object) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / ".env.example").write_text(
            "TARGET_API_BASE_URL=https://example.com\n", encoding="utf-8"
        )

    mocker.patch(
        "openapi_to_mcp.commands.run.generate_project",
        side_effect=fake_generate_project,
    )

    result = runner.invoke(
        cli,
        [
            "run",
            "--openapi-json",
            str(tmp_path / "openapi.yaml"),
            "--output-dir",
            str(output_dir),
            "--origin-allowlist",
            "https://example.com,http://localhost",
            "--host-allowlist",
            "example.com,localhost",
            "--max-concurrency",
            "64",
            "--per-tool-max-concurrency",
            "16",
            "--max-queue-size",
            "512",
            "--queue-timeout-ms",
            "2000",
            "--tool-timeout-ms",
            "45000",
        ],
    )

    assert result.exit_code == 0
    env_contents = (output_dir / ".env").read_text(encoding="utf-8")
    assert "MCP_ALLOWED_ORIGINS=https://example.com,http://localhost" in env_contents
    assert "MCP_ALLOWED_HOSTS=example.com,localhost" in env_contents
    assert "MCP_MAX_CONCURRENCY=64" in env_contents
    assert "MCP_PER_TOOL_MAX_CONCURRENCY=16" in env_contents
    assert "MCP_MAX_QUEUE_SIZE=512" in env_contents
    assert "MCP_QUEUE_TIMEOUT_MS=2000" in env_contents
    assert "MCP_TOOL_TIMEOUT_MS=45000" in env_contents
    assert subprocess_run.call_args_list[0].kwargs["env"]["MCP_MAX_CONCURRENCY"] == "64"


def test_run_cli_runtime_overrides_beat_env_source(
    runner: CliRunner, tmp_path: Path, mocker: MagicMock
) -> None:
    output_dir = tmp_path / "generated"
    subprocess_run = mocker.patch("openapi_to_mcp.commands.run_support.subprocess.run")
    mocker.patch(
        "openapi_to_mcp.commands.run_support.shutil.which", return_value="/usr/bin/tool"
    )

    def fake_generate_project(**_: object) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / ".env.example").write_text(
            "TARGET_API_BASE_URL=https://example.com\n", encoding="utf-8"
        )

    mocker.patch(
        "openapi_to_mcp.commands.run.generate_project",
        side_effect=fake_generate_project,
    )

    result = runner.invoke(
        cli,
        [
            "run",
            "--openapi-json",
            str(tmp_path / "openapi.yaml"),
            "--output-dir",
            str(output_dir),
            "--env-source",
            '{"MCP_MAX_CONCURRENCY":"4"}',
            "--max-concurrency",
            "64",
        ],
    )

    assert result.exit_code == 0
    env_contents = (output_dir / ".env").read_text(encoding="utf-8")
    assert "MCP_MAX_CONCURRENCY=64" in env_contents
    assert subprocess_run.call_args_list[0].kwargs["env"]["MCP_MAX_CONCURRENCY"] == "64"


def test_run_env_source_empty_value_overrides_shell_env(
    runner: CliRunner, tmp_path: Path, mocker: MagicMock
) -> None:
    output_dir = tmp_path / "generated"
    subprocess_run = mocker.patch("openapi_to_mcp.commands.run_support.subprocess.run")
    mocker.patch(
        "openapi_to_mcp.commands.run_support.shutil.which", return_value="/usr/bin/tool"
    )
    mocker.patch.dict(
        "openapi_to_mcp.commands.run_support.os.environ",
        {"MCP_ALLOWED_HOSTS": "from-shell"},
        clear=False,
    )

    def fake_generate_project(**_: object) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / ".env.example").write_text(
            "TARGET_API_BASE_URL=https://example.com\n", encoding="utf-8"
        )

    mocker.patch(
        "openapi_to_mcp.commands.run.generate_project",
        side_effect=fake_generate_project,
    )

    result = runner.invoke(
        cli,
        [
            "run",
            "--openapi-json",
            str(tmp_path / "openapi.yaml"),
            "--output-dir",
            str(output_dir),
            "--env-source",
            '{"MCP_ALLOWED_HOSTS":""}',
        ],
    )

    assert result.exit_code == 0
    env_contents = (output_dir / ".env").read_text(encoding="utf-8")
    assert "MCP_ALLOWED_HOSTS=" in env_contents
    assert subprocess_run.call_args_list[0].kwargs["env"]["MCP_ALLOWED_HOSTS"] == ""
