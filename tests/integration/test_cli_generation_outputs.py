"""CLI integration tests for generated package outputs."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner, Result


def _invoke_streamable_generation(runner: CliRunner, output_dir: Path) -> Result:
    return runner.invoke(
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


def _read_source(output_dir: Path, relative_path: str) -> str:
    return (output_dir / relative_path).read_text(encoding="utf-8")


def test_generate_streamable_http_end_to_end(runner: CliRunner, tmp_path: Path) -> None:
    output_dir = tmp_path / "generated-streamable"
    result = _invoke_streamable_generation(runner, output_dir)

    assert result.exit_code == 0
    assert (output_dir / "package.json").exists()
    assert (output_dir / "src" / "transport.ts").exists()
    assert (output_dir / "generation_report.json").exists()
    assert (output_dir / "src" / "runtime" / "generated.ts").exists()
    assert (output_dir / "src" / "runtime" / "executor.ts").exists()

    package_json = json.loads(_read_source(output_dir, "package.json"))
    index_source = _read_source(output_dir, "src/index.ts")
    transport_source = _read_source(output_dir, "src/transport.ts")
    server_source = _read_source(output_dir, "src/server.ts")
    http_transport = _read_source(output_dir, "src/runtime/http_transport.ts")
    generated_source = _read_source(output_dir, "src/runtime/generated.ts")
    serialization = _read_source(output_dir, "src/runtime/serialization.ts")
    assert package_json["engines"] == {"node": ">=22"}
    assert "quiet: true" in index_source
    assert "StreamableHTTPServerTransport" in transport_source
    assert "SSEServerTransport" not in transport_source
    assert "encodeURIComponent" in serialization
    assert "_original_" not in generated_source
    assert "const toolRuntimeData = {" in generated_source
    assert "new ToolExecutor()" in server_source
    assert "./runtime/http_transport.js" in transport_source
    assert "extractHostFromHeaderValue" in http_transport
    assert "first.split(':')[0]" not in http_transport
    assert "process.once('SIGINT'" in server_source
    assert "process.once('SIGTERM'" in server_source
    assert "process.on('SIGINT'" not in server_source
    assert "process.on('SIGTERM'" not in server_source

    report = json.loads(_read_source(output_dir, "generation_report.json"))
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
    package_json = json.loads(_read_source(output_dir, "package.json"))
    assert "express" not in package_json["dependencies"]
    assert "@types/express" not in package_json["devDependencies"]
    assert package_json["engines"] == {"node": ">=22"}
    assert "quiet: true" in _read_source(output_dir, "src/index.ts")
    assert "StdioServerTransport" in _read_source(output_dir, "src/transport.ts")


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
    env_example = _read_source(output_dir, ".env.example")
    assert "AUTH_HEADERAPIKEY_API_KEY=" in env_example
    assert "AUTH_QUERYAPIKEY_API_KEY=" in env_example
    assert "AUTH_COOKIEAPIKEY_API_KEY=" in env_example
    assert "AUTH_BEARERAUTH_TOKEN=" in env_example
