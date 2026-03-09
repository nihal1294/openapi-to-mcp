from __future__ import annotations

import json
from typing import TYPE_CHECKING

from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner


def test_generate_runtime_validation_input_emits_ajv_and_validator(
    runner: CliRunner, tmp_path: Path
) -> None:
    output_dir = tmp_path / "generated-validation-input"

    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            "tests/resources/test_openapi.yaml",
            "--output-dir",
            str(output_dir),
            "--runtime-validation",
            "input",
        ],
    )

    assert result.exit_code == 0
    package_json = json.loads((output_dir / "package.json").read_text(encoding="utf-8"))
    validation_source = (output_dir / "src" / "runtime" / "validation.ts").read_text(
        encoding="utf-8"
    )

    assert "ajv" in package_json["dependencies"]
    assert "Ajv" in validation_source
    assert "Input validation failed:" in validation_source


def test_generate_runtime_validation_none_omits_ajv_and_validator(
    runner: CliRunner, tmp_path: Path
) -> None:
    output_dir = tmp_path / "generated-validation-none"

    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            "tests/resources/test_openapi.yaml",
            "--output-dir",
            str(output_dir),
            "--runtime-validation",
            "none",
        ],
    )

    assert result.exit_code == 0
    package_json = json.loads((output_dir / "package.json").read_text(encoding="utf-8"))
    validation_source = (output_dir / "src" / "runtime" / "validation.ts").read_text(
        encoding="utf-8"
    )

    assert "ajv" not in package_json["dependencies"]
    assert "Ajv" not in validation_source
