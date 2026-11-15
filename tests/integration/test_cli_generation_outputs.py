"""CLI integration tests for generated package outputs."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest

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
    assert package_json["dependencies"]["@modelcontextprotocol/server"] == "^2.4.0"
    assert package_json["dependencies"]["@modelcontextprotocol/node"] == "^2.1.2"
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
    assert package_json["dependencies"]["@modelcontextprotocol/server"] == "^2.4.0"
    assert "@types/express" not in package_json["devDependencies"]
    assert package_json["engines"] == {"node": ">=22"}
    assert "quiet: true" in _read_source(output_dir, "src/index.ts")
    assert "serveStdio" in _read_source(output_dir, "src/transport.ts")


@pytest.mark.parametrize(
    ("transport", "minimum_dependencies"),
    [
        ("stdio", {"@modelcontextprotocol/server": "2.4.0"}),
        (
            "streamable-http",
            {
                "@modelcontextprotocol/server": "2.4.0",
                "@modelcontextprotocol/node": "2.1.2",
            },
        ),
    ],
)
def test_generated_server_builds_with_minimum_mcp_sdk_versions(
    runner: CliRunner,
    tmp_path: Path,
    transport: str,
    minimum_dependencies: dict[str, str],
) -> None:
    """Generated projects compile with the declared SDK floors, not only newer resolutions."""
    output_dir = tmp_path / f"generated-minimum-{transport}"
    arguments = [
        "generate",
        "--openapi-json",
        "tests/resources/test_openapi.yaml",
        "--output-dir",
        str(output_dir),
        "--transport",
        transport,
    ]
    if transport == "streamable-http":
        arguments.extend(
            ["--host", "127.0.0.1", "--port", "8080", "--mcp-endpoint", "/mcp"]
        )
    result = runner.invoke(cli, arguments)
    assert result.exit_code == 0, result.output

    package_path = output_dir / "package.json"
    package_json = json.loads(package_path.read_text(encoding="utf-8"))
    package_json["dependencies"].update(minimum_dependencies)
    package_path.write_text(json.dumps(package_json, indent=2) + "\n", encoding="utf-8")

    npm = shutil.which("npm")
    assert npm is not None, "npm is required for generated SDK compatibility tests"
    subprocess.run(  # noqa: S603
        [npm, "install", "--ignore-scripts", "--no-audit", "--no-fund"],
        cwd=output_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    compiled = subprocess.run(  # noqa: S603
        [npm, "run", "build"],
        cwd=output_dir,
        check=False,
        capture_output=True,
        text=True,
    )
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr


def test_regenerating_http_output_as_stdio_removes_http_runtime(
    runner: CliRunner, tmp_path: Path
) -> None:
    output_dir = tmp_path / "regenerated-stdio"
    assert _invoke_streamable_generation(runner, output_dir).exit_code == 0
    health_runtime = output_dir / "src" / "runtime" / "health.ts"
    custom_tools = output_dir / "src" / "custom" / "tools.ts"
    assert health_runtime.exists()
    preserved_custom_tools = custom_tools.read_text(encoding="utf-8")
    custom_tools.write_text(
        f"{preserved_custom_tools}\n// Preserved customization.\n", encoding="utf-8"
    )

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

    assert result.exit_code == 0, result.output
    assert not health_runtime.exists()
    assert custom_tools.read_text(encoding="utf-8").endswith(
        "// Preserved customization.\n"
    )
    package_json = json.loads(_read_source(output_dir, "package.json"))
    assert "express" not in package_json["dependencies"]

    node_modules = output_dir / "node_modules"
    if node_modules.exists():
        shutil.rmtree(node_modules)
    (output_dir / "package-lock.json").unlink(missing_ok=True)
    npm = shutil.which("npm")
    assert npm is not None
    subprocess.run(  # noqa: S603
        [npm, "install", "--ignore-scripts", "--no-audit", "--no-fund"],
        cwd=output_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    compiled = subprocess.run(  # noqa: S603
        [npm, "run", "build"],
        cwd=output_dir,
        check=False,
        capture_output=True,
        text=True,
    )
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr


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
    assert "AUTH_BASICAUTH_USERNAME=" in env_example
    assert "AUTH_BASICAUTH_PASSWORD=" in env_example
