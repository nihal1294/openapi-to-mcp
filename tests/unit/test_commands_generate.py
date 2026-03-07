from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from openapi_to_mcp.cli import cli
from openapi_to_mcp.common.exceptions import NoToolsMappedError

if TYPE_CHECKING:
    from pathlib import Path
    from unittest.mock import MagicMock


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_generate_handles_no_tools_mapped_cleanly(
    runner: CliRunner, tmp_path: Path, mocker: MagicMock
) -> None:
    mocker.patch(
        "openapi_to_mcp.commands.generate.generate_project",
        side_effect=NoToolsMappedError("No tools were mapped from the OpenAPI spec."),
    )

    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            str(tmp_path / "openapi.yaml"),
            "--output-dir",
            str(tmp_path / "generated"),
        ],
    )

    assert result.exit_code == 0
    assert "No tools were mapped from the OpenAPI spec." in result.output
    assert "Traceback" not in result.output
