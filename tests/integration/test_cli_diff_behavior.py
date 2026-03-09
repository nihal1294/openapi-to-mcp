from __future__ import annotations

import importlib
import json
from typing import TYPE_CHECKING, Any

from openapi_to_mcp.cli import cli
from openapi_to_mcp.common import MappingError

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from click.testing import CliRunner


def test_diff_reports_no_changes_when_specs_match(
    runner: CliRunner, tmp_path: Path
) -> None:
    spec_path = _write_json(tmp_path / "same.json", _valid_spec("listPets"))

    result = runner.invoke(
        cli,
        [
            "diff",
            "--before-openapi-json",
            str(spec_path),
            "--after-openapi-json",
            str(spec_path),
        ],
    )

    assert result.exit_code == 0
    assert "No MCP-surface changes detected." in result.output


def test_diff_default_fail_on_none_keeps_zero_exit_code(
    runner: CliRunner, tmp_path: Path
) -> None:
    before_path = _write_json(tmp_path / "before.json", _valid_spec("listPets"))
    after_path = _write_json(tmp_path / "after.json", _valid_spec("fetchPets"))

    result = runner.invoke(
        cli,
        [
            "diff",
            "--before-openapi-json",
            str(before_path),
            "--after-openapi-json",
            str(after_path),
        ],
    )

    assert result.exit_code == 0
    assert "tool_renamed" in result.output


def test_diff_fails_on_invalid_spec_source(runner: CliRunner, tmp_path: Path) -> None:
    after_path = _write_json(tmp_path / "after.json", _valid_spec("listPets"))

    result = runner.invoke(
        cli,
        [
            "diff",
            "--before-openapi-json",
            str(tmp_path / "missing.json"),
            "--after-openapi-json",
            str(after_path),
        ],
    )

    assert result.exit_code == 1
    assert "Failed to load spec" in result.output


def test_diff_fails_when_schema_skips_would_make_result_incomplete(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before_path = _write_json(tmp_path / "before.json", _valid_spec("listPets"))
    after_path = _write_json(tmp_path / "after.json", _valid_spec("fetchPets"))
    diff_module = importlib.import_module("openapi_to_mcp.commands.diff")
    monkeypatch.setattr(diff_module.DiffAnalyzer, "analyze", _raise_mapping_error)

    result = runner.invoke(
        cli,
        [
            "diff",
            "--before-openapi-json",
            str(before_path),
            "--after-openapi-json",
            str(after_path),
        ],
    )

    assert result.exit_code == 1
    assert "Unable to diff MCP surface" in result.output
    assert "doctor" in result.output


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _valid_spec(operation_id: str) -> dict[str, Any]:
    return {
        "openapi": "3.0.0",
        "info": {"title": "Diff Behavior", "version": "1.0.0"},
        "servers": [{"url": "https://example.com"}],
        "paths": {
            "/pets": {
                "get": {
                    "operationId": operation_id,
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }


def _raise_mapping_error(*_: object) -> None:
    raise MappingError("Spec mapping skipped operation schema(s) during diff.")
