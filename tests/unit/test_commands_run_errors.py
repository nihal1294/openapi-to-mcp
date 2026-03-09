from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from openapi_to_mcp.cli import cli
from openapi_to_mcp.common.exceptions import SpecLoaderError

if TYPE_CHECKING:
    from pathlib import Path
    from unittest.mock import MagicMock


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_run_reports_generate_project_failures_cleanly(
    runner: CliRunner, tmp_path: Path, mocker: MagicMock
) -> None:
    mocker.patch(
        "openapi_to_mcp.commands.run_support.shutil.which",
        return_value="/usr/bin/tool",
    )
    mocker.patch(
        "openapi_to_mcp.commands.run.generate_project",
        side_effect=SpecLoaderError("Broken spec"),
    )

    result = runner.invoke(
        cli,
        ["run", "--openapi-json", str(tmp_path / "openapi.yaml")],
    )

    assert result.exit_code != 0
    assert "Broken spec" in result.output
    assert "Traceback" not in result.output


def test_run_reports_invalid_env_source_cleanly(
    runner: CliRunner, tmp_path: Path, mocker: MagicMock
) -> None:
    output_dir = tmp_path / "generated"
    mocker.patch(
        "openapi_to_mcp.commands.run_support.shutil.which",
        return_value="/usr/bin/tool",
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
            str(tmp_path / "missing.env"),
        ],
    )

    assert result.exit_code != 0
    assert "File not found for env source" in result.output
    assert "Traceback" not in result.output


def test_run_rejects_env_values_with_newlines(
    runner: CliRunner, tmp_path: Path, mocker: MagicMock
) -> None:
    output_dir = tmp_path / "generated"
    mocker.patch(
        "openapi_to_mcp.commands.run_support.shutil.which",
        return_value="/usr/bin/tool",
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
            json.dumps({"MCP_ALLOWED_HOSTS": "ok\nBAD=1"}),
        ],
    )

    assert result.exit_code != 0
    assert "MCP_ALLOWED_HOSTS contains a newline" in result.output
    assert "Traceback" not in result.output
