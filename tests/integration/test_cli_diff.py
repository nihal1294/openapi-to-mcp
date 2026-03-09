from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner


def test_diff_reports_text_changes_and_fail_on_breaking(
    runner: CliRunner, tmp_path: Path
) -> None:
    before_path = _write_json(
        tmp_path / "before.json",
        _spec(
            {
                "/pets": {
                    "get": {
                        "operationId": "listPets",
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            }
        ),
    )
    after_path = _write_json(
        tmp_path / "after.json",
        _spec(
            {
                "/pets": {
                    "get": {
                        "operationId": "fetchPets",
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            }
        ),
    )

    result = runner.invoke(
        cli,
        [
            "diff",
            "--before-openapi-json",
            str(before_path),
            "--after-openapi-json",
            str(after_path),
            "--fail-on",
            "breaking",
        ],
    )

    assert result.exit_code == 2
    assert "Diff Summary" in result.output
    assert "tool_renamed" in result.output


def test_diff_json_output_is_machine_readable(
    runner: CliRunner, tmp_path: Path
) -> None:
    before_path = _write_json(
        tmp_path / "before.json",
        _spec(
            {
                "/pets": {
                    "get": {
                        "operationId": "listPets",
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            }
        ),
    )
    after_path = _write_json(
        tmp_path / "after.json",
        _spec(
            {
                "/orders": {
                    "get": {
                        "operationId": "listOrders",
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            }
        ),
    )

    result = runner.invoke(
        cli,
        [
            "diff",
            "--before-openapi-json",
            str(before_path),
            "--after-openapi-json",
            str(after_path),
            "--format",
            "json",
        ],
    )

    payload = json.loads(result.stdout)

    assert result.exit_code == 0
    assert payload["breaking"] == 1
    assert payload["non_breaking"] == 1
    assert {change["code"] for change in payload["changes"]} == {
        "tool_added",
        "tool_removed",
    }


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _spec(paths: dict[str, Any]) -> dict[str, Any]:
    return {
        "openapi": "3.0.0",
        "info": {"title": "Diff Cli", "version": "1.0.0"},
        "servers": [{"url": "https://example.com"}],
        "paths": paths,
    }
