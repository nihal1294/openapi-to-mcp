from __future__ import annotations

import json
from typing import TYPE_CHECKING

from openapi_to_mcp.cli import cli
from openapi_to_mcp.mapping.mapper import Mapper

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


def _write_mapping_policy_spec(path: Path) -> Path:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Mapping Policy API", "version": "1.0.0"},
        "servers": [{"url": "https://example.com/api"}],
        "paths": {
            "/ok": {
                "get": {
                    "operationId": "okTool",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/bad": {
                "get": {
                    "operationId": "badTool",
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
    assert (output_dir / "src" / "runtime" / "generated.ts").exists()
    assert (output_dir / "src" / "runtime" / "executor.ts").exists()

    package_json = json.loads((output_dir / "package.json").read_text(encoding="utf-8"))
    index_source = (output_dir / "src" / "index.ts").read_text(encoding="utf-8")
    transport_source = (output_dir / "src" / "transport.ts").read_text(encoding="utf-8")
    server_source = (output_dir / "src" / "server.ts").read_text(encoding="utf-8")
    http_transport_source = (
        output_dir / "src" / "runtime" / "http_transport.ts"
    ).read_text(encoding="utf-8")
    generated_source = (output_dir / "src" / "runtime" / "generated.ts").read_text(
        encoding="utf-8"
    )
    serialization_source = (
        output_dir / "src" / "runtime" / "serialization.ts"
    ).read_text(encoding="utf-8")
    assert package_json["engines"] == {"node": ">=18"}
    assert "quiet: true" in index_source
    assert "StreamableHTTPServerTransport" in transport_source
    assert "SSEServerTransport" not in transport_source
    assert "encodeURIComponent" in serialization_source
    assert "_original_" not in generated_source
    assert "const toolRuntimeData = {" in generated_source
    assert "new ToolExecutor()" in server_source
    assert "./runtime/http_transport.js" in transport_source
    assert "extractHostFromHeaderValue" in http_transport_source
    assert "first.split(':')[0]" not in http_transport_source
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
    assert package_json["engines"] == {"node": ">=18"}

    index_source = (output_dir / "src" / "index.ts").read_text(encoding="utf-8")
    transport_source = (output_dir / "src" / "transport.ts").read_text(encoding="utf-8")
    assert "quiet: true" in index_source
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
    assert "Duplicate tool name detected" in result.output
    assert "Traceback" not in result.output
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
    spec_path = _write_duplicate_operation_spec(tmp_path / "duplicate.json")
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
    spec_path = _write_mapping_policy_spec(tmp_path / "mapping-policy.json")
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
    spec_path = _write_mapping_policy_spec(tmp_path / "mapping-policy.json")
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
