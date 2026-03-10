from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

import yaml

from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from click.testing import CliRunner


def _normalize_output(text: str) -> str:
    return " ".join(re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text).split())


def test_generate_uses_policy_file_for_rename_auth_and_execution(
    runner: CliRunner, tmp_path: Path
) -> None:
    spec_path = _write_spec(tmp_path / "openapi.json")
    config_path = _write_policy(
        tmp_path / "mcpgen.yaml",
        {
            "tools": {"rename": {"operations": {"GET /test": "renamedTestTool"}}},
            "auth": {
                "operations": {
                    "GET /test": {
                        "security": [{"bearerAuth": []}],
                        "security_schemes": {
                            "bearerAuth": {"type": "http", "scheme": "bearer"}
                        },
                    }
                }
            },
            "execution": {
                "operations": {"GET /test": {"max_concurrency": 3, "timeout_ms": 12000}}
            },
        },
    )
    output_dir = tmp_path / "generated"

    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            str(spec_path),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    generated_source = (output_dir / "src" / "runtime" / "generated.ts").read_text(
        encoding="utf-8"
    )
    env_example = (output_dir / ".env.example").read_text(encoding="utf-8")
    assert '"renamedTestTool"' in generated_source
    assert '"security": [' in generated_source
    assert '"securitySchemes": {' in generated_source
    assert '"execution": {' in generated_source
    assert '"maxConcurrency": 3' in generated_source
    assert '"timeoutMs": 12000' in generated_source
    assert "AUTH_BEARERAUTH_TOKEN=" in env_example


def test_generate_cli_values_override_policy_defaults(
    runner: CliRunner, tmp_path: Path
) -> None:
    spec_path = _write_spec(tmp_path / "openapi.json")
    config_path = _write_policy(
        tmp_path / "mcpgen.yaml",
        {
            "generate": {
                "transport": "stdio",
                "runtime_validation": "none",
            }
        },
    )
    output_dir = tmp_path / "generated"

    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            str(spec_path),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
            "--transport",
            "streamable-http",
            "--runtime-validation",
            "input",
        ],
    )

    assert result.exit_code == 0
    transport_source = (output_dir / "src" / "transport.ts").read_text(encoding="utf-8")
    package_json = json.loads((output_dir / "package.json").read_text(encoding="utf-8"))
    assert "StreamableHTTPServerTransport" in transport_source
    assert "ajv" in package_json["dependencies"]


def test_generate_autodiscovers_mcpgen_yaml(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec_path = _write_spec(tmp_path / "openapi.json")
    _write_policy(
        tmp_path / "mcpgen.yaml",
        {"tools": {"rename": {"names": {"testConversionTool": "autoNamed"}}}},
    )
    output_dir = tmp_path / "generated"
    monkeypatch.chdir(tmp_path)

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

    assert result.exit_code == 0
    generated_source = (output_dir / "src" / "runtime" / "generated.ts").read_text(
        encoding="utf-8"
    )
    assert '"autoNamed"' in generated_source


def test_generate_fails_cleanly_when_policy_filters_all_tools(
    runner: CliRunner, tmp_path: Path
) -> None:
    spec_path = _write_spec(tmp_path / "openapi.json")
    config_path = _write_policy(
        tmp_path / "mcpgen.yaml",
        {"tools": {"include": {"operations": ["POST /missing"]}}},
    )
    output_dir = tmp_path / "generated"

    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            str(spec_path),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code != 0
    assert (
        "No tools remain after applying the configured mcpgen policy."
        in _normalize_output(result.output)
    )


def _write_spec(path: Path) -> Path:
    payload = {
        "openapi": "3.0.0",
        "info": {"title": "Policy Test", "version": "1.0.0"},
        "servers": [{"url": "https://example.com"}],
        "paths": {
            "/test": {
                "get": {
                    "operationId": "testConversionTool",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_policy(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path
