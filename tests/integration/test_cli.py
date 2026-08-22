from __future__ import annotations

import json
from typing import TYPE_CHECKING

from openapi_to_mcp.cli import cli
from openapi_to_mcp.mapping.mapper import Mapper
from tests.integration.cli_generation_specs import (
    write_duplicate_operation_spec,
    write_mapping_policy_spec,
)

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner


def test_generate_strict_generated_name_collision_fails(
    runner: CliRunner, tmp_path: Path
) -> None:
    spec_path = write_duplicate_operation_spec(tmp_path / "duplicate.json")
    output_dir = tmp_path / "strict-fail-output"

    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            str(spec_path),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code != 0
    assert "Duplicate tool name detected" in result.output
    assert "Traceback" not in result.output
    assert not (output_dir / "generation_report.json").exists()


def test_generate_no_strict_generated_name_collision_dedupes_and_reports(
    runner: CliRunner, tmp_path: Path
) -> None:
    spec_path = write_duplicate_operation_spec(tmp_path / "duplicate.json")
    output_dir = tmp_path / "non-strict-output"

    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            str(spec_path),
            "--output-dir",
            str(output_dir),
            "--no-strict",
        ],
    )

    assert result.exit_code == 0

    report = json.loads((output_dir / "generation_report.json").read_text())
    assert report["strict_mode"] is False
    assert report["mapped_tools"] == 2
    assert report["skipped_operations"] == []
    assert any("deduped" in warning for warning in report["warnings"])
    assert "TARGET_API_BASE_URL=https://example.com/api" in (
        output_dir / ".env.example"
    ).read_text(encoding="utf-8")

    generated_source = (output_dir / "src" / "runtime" / "generated.ts").read_text(
        encoding="utf-8"
    )
    assert "get_a_b_2" in generated_source


def test_generate_no_strict_generated_name_collision_with_mapping_fail_exits(
    runner: CliRunner, tmp_path: Path
) -> None:
    spec_path = write_duplicate_operation_spec(tmp_path / "duplicate.json")
    output_dir = tmp_path / "mapping-fail-output"

    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            str(spec_path),
            "--output-dir",
            str(output_dir),
            "--no-strict",
            "--on-mapping-error",
            "fail",
        ],
    )

    assert result.exit_code != 0
    assert not (output_dir / "generation_report.json").exists()


def test_generate_strict_on_mapping_error_skip_reports(
    runner: CliRunner, tmp_path: Path, monkeypatch: object
) -> None:
    spec_path = write_mapping_policy_spec(tmp_path / "mapping-policy.json")
    output_dir = tmp_path / "mapping-skip-output"

    original = Mapper._map_operation_to_tool

    def fail_bad_operation(
        self: Mapper,
        method: str,
        path: str,
        operation: dict[str, object],
        parameters: list[dict[str, object]],
    ) -> dict[str, object]:
        if path == "/bad":
            raise RuntimeError("Injected mapping failure")
        return original(self, method, path, operation, parameters)

    monkeypatch.setattr(Mapper, "_map_operation_to_tool", fail_bad_operation)

    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            str(spec_path),
            "--output-dir",
            str(output_dir),
            "--on-mapping-error",
            "skip",
        ],
    )

    assert result.exit_code == 0

    report = json.loads((output_dir / "generation_report.json").read_text())
    assert report["on_mapping_error"] == "skip"
    assert report["mapped_tools"] == 1
    assert report["skipped_operations"][0]["path"] == "/bad"


def test_generate_no_strict_on_mapping_error_fail_exits(
    runner: CliRunner, tmp_path: Path, monkeypatch: object
) -> None:
    spec_path = write_mapping_policy_spec(tmp_path / "mapping-policy.json")
    output_dir = tmp_path / "mapping-fail-output"

    original = Mapper._map_operation_to_tool

    def fail_bad_operation(
        self: Mapper,
        method: str,
        path: str,
        operation: dict[str, object],
        parameters: list[dict[str, object]],
    ) -> dict[str, object]:
        if path == "/bad":
            raise RuntimeError("Injected mapping failure")
        return original(self, method, path, operation, parameters)

    monkeypatch.setattr(Mapper, "_map_operation_to_tool", fail_bad_operation)

    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            str(spec_path),
            "--output-dir",
            str(output_dir),
            "--no-strict",
            "--on-mapping-error",
            "fail",
        ],
    )

    assert result.exit_code != 0
    assert not (output_dir / "generation_report.json").exists()
