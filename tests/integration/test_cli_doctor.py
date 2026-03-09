from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _extract_json(output: str) -> dict[str, Any]:
    cleaned = _ANSI_RE.sub("", output).strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return json.loads(cleaned)
    lines: list[str] = []
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not (line.startswith("│") and line.endswith("│")):
            continue
        inner = line[1:-1].strip()
        if inner.startswith(("{", "}", "[", "]", '"')):
            lines.append(inner)
    return json.loads("\n".join(lines))


def test_doctor_clean_spec_exits_zero(runner: CliRunner, tmp_path: Path) -> None:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Doctor Clean", "version": "1.0.0"},
        "servers": [{"url": "https://example.com"}],
        "paths": {
            "/pets": {
                "get": {
                    "operationId": "listPets",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    spec_path = _write_json(tmp_path / "clean.json", spec)

    result = runner.invoke(cli, ["doctor", "--openapi-json", str(spec_path)])

    assert result.exit_code == 0
    assert "No readiness issues found." in result.output


def test_doctor_warning_report_exits_two(runner: CliRunner, tmp_path: Path) -> None:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Doctor Warnings", "version": "1.0.0"},
        "paths": {
            "/pets": {
                "get": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "oneOf": [
                                        {
                                            "type": "object",
                                            "properties": {"a": {"type": "string"}},
                                        },
                                        {
                                            "type": "object",
                                            "properties": {"b": {"type": "string"}},
                                        },
                                    ]
                                }
                            }
                        }
                    },
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    spec_path = _write_json(tmp_path / "warnings.json", spec)

    result = runner.invoke(cli, ["doctor", "--openapi-json", str(spec_path)])

    assert result.exit_code == 2
    assert "missing_operation_id" in result.output
    assert "missing_base_url" in result.output
    assert "risky_union_schema" in result.output


def test_doctor_error_report_exits_three(runner: CliRunner, tmp_path: Path) -> None:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Doctor Errors", "version": "1.0.0"},
        "servers": [{"url": "https://example.com"}],
        "components": {
            "securitySchemes": {"basicAuth": {"type": "http", "scheme": "basic"}}
        },
        "paths": {
            "/a-b": {
                "get": {
                    "responses": {"200": {"description": "OK"}},
                    "security": [{"basicAuth": []}],
                }
            },
            "/a_b": {
                "get": {
                    "responses": {"200": {"description": "OK"}},
                    "security": [{"missingScheme": []}],
                }
            },
        },
    }
    spec_path = _write_json(tmp_path / "errors.json", spec)

    result = runner.invoke(cli, ["doctor", "--openapi-json", str(spec_path)])

    assert result.exit_code == 3
    assert "tool_name_collision" in result.output
    assert "undefined_security_scheme" in result.output
    assert "unsupported_http_auth" in result.output


def test_doctor_json_output_is_structured(runner: CliRunner, tmp_path: Path) -> None:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Doctor Json", "version": "1.0.0"},
        "paths": {},
    }
    spec_path = _write_json(tmp_path / "json.json", spec)

    result = runner.invoke(
        cli,
        ["doctor", "--openapi-json", str(spec_path), "--format", "json"],
    )

    assert result.exit_code == 3
    payload = _extract_json(result.stdout)

    assert payload["exit_code"] == 3
    assert {issue["code"] for issue in payload["issues"]} == {
        "missing_base_url",
        "no_http_operations",
    }


def test_doctor_invalid_source_reports_spec_load_failure(
    runner: CliRunner, tmp_path: Path
) -> None:
    missing_path = tmp_path / "missing.yaml"

    result = runner.invoke(
        cli,
        ["doctor", "--openapi-json", str(missing_path), "--format", "json"],
    )

    assert result.exit_code == 3
    payload = _extract_json(result.stdout)

    assert payload["exit_code"] == 3
    assert payload["issues"][0]["code"] == "spec_load_failed"
    assert payload["issues"][0]["location"] == str(missing_path)


def test_doctor_explicit_text_format_matches_default(
    runner: CliRunner, tmp_path: Path
) -> None:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Doctor Text", "version": "1.0.0"},
        "paths": {
            "/pets": {"get": {"responses": {"200": {"description": "OK"}}}},
        },
    }
    spec_path = _write_json(tmp_path / "text.json", spec)

    result = runner.invoke(
        cli,
        ["doctor", "--openapi-json", str(spec_path), "--format", "text"],
    )

    assert result.exit_code == 2
    assert "Doctor Summary" in result.output
    assert "missing_base_url" in result.output
