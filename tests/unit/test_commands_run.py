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


def test_run_requires_resolved_target_api_base_url(
    runner: CliRunner, tmp_path: Path, mocker: MagicMock
) -> None:
    output_dir = tmp_path / "generated"
    mocker.patch(
        "openapi_to_mcp.commands.run_support.shutil.which", return_value="/usr/bin/tool"
    )
    mocker.patch("openapi_to_mcp.commands.run_support.subprocess.run")

    def fake_generate_project(**_: object) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / ".env.example").write_text(
            "TARGET_API_BASE_URL=YOUR_API_BASE_URL_HERE\n", encoding="utf-8"
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

    assert result.exit_code != 0
    assert "TARGET_API_BASE_URL is unresolved" in result.output


def test_run_generates_env_and_executes_runtime_steps(
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
            "--target-api-base-url",
            "https://override.example.com",
            "--env-source",
            '{"AUTH_TEST_API_KEY":"secret"}',
        ],
    )

    assert result.exit_code == 0
    assert subprocess_run.call_count == 3
    assert subprocess_run.call_args_list[0].args[0] == ["npm", "install"]
    assert subprocess_run.call_args_list[1].args[0] == ["npm", "run", "build"]
    assert subprocess_run.call_args_list[2].args[0] == ["node", "build/index.js"]

    env_contents = (output_dir / ".env").read_text(encoding="utf-8")
    assert "TARGET_API_BASE_URL=https://override.example.com" in env_contents
    assert "AUTH_TEST_API_KEY=secret" in env_contents


def test_run_accepts_target_api_base_url_without_env_source(
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
            "TARGET_API_BASE_URL=YOUR_API_BASE_URL_HERE\n", encoding="utf-8"
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
            "--target-api-base-url",
            "https://override.example.com",
        ],
    )

    assert result.exit_code == 0
    assert subprocess_run.call_count == 3
    env_contents = (output_dir / ".env").read_text(encoding="utf-8")
    assert "TARGET_API_BASE_URL=https://override.example.com" in env_contents
