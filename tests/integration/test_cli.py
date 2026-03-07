from __future__ import annotations

import json
from typing import TYPE_CHECKING

from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner


def _write_duplicate_operation_spec(path: Path) -> Path:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Generated Name Collision API", "version": "1.0.0"},
        "servers": [{"url": "https://example.com/api"}],
        "paths": {
            "/a-b": {
                "get": {
                    "summary": "Dash path",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/a_b": {
                "get": {
                    "summary": "Underscore path",
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
    }
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path


def test_generate_streamable_http_end_to_end(runner: CliRunner, tmp_path: Path) -> None:
    output_dir = tmp_path / "generated-streamable"

    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            "tests/resources/test_openapi.yaml",
            "--output-dir",
            str(output_dir),
            "--transport",
            "streamable-http",
            "--host",
            "127.0.0.1",
            "--port",
            "8080",
            "--mcp-endpoint",
            "/mcp",
        ],
    )

    assert result.exit_code == 0
    assert (output_dir / "package.json").exists()
    assert (output_dir / "src" / "transport.ts").exists()
    assert (output_dir / "generation_report.json").exists()

    transport_source = (output_dir / "src" / "transport.ts").read_text(encoding="utf-8")
    server_source = (output_dir / "src" / "server.ts").read_text(encoding="utf-8")
    assert "StreamableHTTPServerTransport" in transport_source
    assert "SSEServerTransport" not in transport_source
    assert "encodeURIComponent" in server_source
    assert "extractHostFromHeaderValue" in transport_source
    assert "first.split(':')[0]" not in transport_source
    assert "process.once('SIGINT'" in server_source
    assert "process.once('SIGTERM'" in server_source
    assert "process.on('SIGINT'" not in server_source
    assert "process.on('SIGTERM'" not in server_source

    report = json.loads((output_dir / "generation_report.json").read_text())
    assert report["strict_mode"] is True
    assert report["transport"] == "streamable-http"
    assert report["mapped_tools"] >= 1


def test_generate_stdio_omits_http_dependencies(
    runner: CliRunner, tmp_path: Path
) -> None:
    output_dir = tmp_path / "generated-stdio"

    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            "tests/resources/test_openapi.yaml",
            "--output-dir",
            str(output_dir),
            "--transport",
            "stdio",
        ],
    )

    assert result.exit_code == 0

    package_json = json.loads((output_dir / "package.json").read_text(encoding="utf-8"))
    assert "express" not in package_json["dependencies"]
    assert "@types/express" not in package_json["devDependencies"]

    transport_source = (output_dir / "src" / "transport.ts").read_text(encoding="utf-8")
    assert "StdioServerTransport" in transport_source


def test_generate_auth_fixture_emits_auth_env_vars(
    runner: CliRunner, tmp_path: Path
) -> None:
    output_dir = tmp_path / "generated-auth"

    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            "tests/resources/auth_openapi.yaml",
            "--output-dir",
            str(output_dir),
            "--transport",
            "stdio",
        ],
    )

    assert result.exit_code == 0
    env_example = (output_dir / ".env.example").read_text(encoding="utf-8")
    assert "AUTH_HEADERAPIKEY_API_KEY=" in env_example
    assert "AUTH_QUERYAPIKEY_API_KEY=" in env_example
    assert "AUTH_COOKIEAPIKEY_API_KEY=" in env_example
    assert "AUTH_BEARERAUTH_TOKEN=" in env_example


def test_generate_strict_generated_name_collision_fails(
    runner: CliRunner, tmp_path: Path
) -> None:
    spec_path = _write_duplicate_operation_spec(tmp_path / "duplicate.json")
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
    assert not (output_dir / "generation_report.json").exists()


def test_generate_no_strict_generated_name_collision_dedupes_and_reports(
    runner: CliRunner, tmp_path: Path
) -> None:
    spec_path = _write_duplicate_operation_spec(tmp_path / "duplicate.json")
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

    server_source = (output_dir / "src" / "server.ts").read_text(encoding="utf-8")
    assert "get_a_b_2" in server_source
