"""Conditional telemetry generation and policy precedence."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner


def test_telemetry_policy_cli_override_and_regeneration(
    runner: CliRunner, tmp_path: Path
) -> None:
    output = tmp_path / "generated"
    policy = tmp_path / "mcpgen.yaml"
    policy.write_text("generate:\n  telemetry: opentelemetry\n")
    args = [
        "generate",
        "--openapi-json",
        "tests/resources/test_openapi.yaml",
        "--output-dir",
        str(output),
        "--config",
        str(policy),
        "--transport",
        "stdio",
    ]
    result = runner.invoke(cli, args)
    assert result.exit_code == 0, result.output
    custom = output / "src/custom/tools.ts"
    custom.write_text("// user customization\n")
    assert (output / "src/runtime/telemetry.ts").exists()
    manifest = json.loads((output / "package.json").read_text())
    assert manifest["engines"]["node"] == ">=22.15.0"
    assert "@opentelemetry/sdk-node" in manifest["dependencies"]
    result = runner.invoke(cli, [*args, "--telemetry", "off"])
    assert result.exit_code == 0, result.output
    assert custom.read_text() == "// user customization\n"
    assert not (output / "src/runtime/telemetry.ts").exists()
    assert "telemetry" not in (output / "src/index.ts").read_text()
    assert "MCP_OTEL" not in (output / ".env.example").read_text()
    manifest = json.loads((output / "package.json").read_text())
    assert manifest["engines"]["node"] == ">=22"
    assert not any(
        name.startswith("@opentelemetry/") for name in manifest["dependencies"]
    )


def test_invalid_telemetry_policy_fails(runner: CliRunner, tmp_path: Path) -> None:
    policy = tmp_path / "mcpgen.yaml"
    policy.write_text("generate:\n  telemetry: unsupported\n")
    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            "tests/resources/test_openapi.yaml",
            "--output-dir",
            str(tmp_path / "out"),
            "--config",
            str(policy),
        ],
    )
    assert result.exit_code != 0
    assert "generate.telemetry" in result.output


def test_off_preserves_unowned_telemetry_file(
    runner: CliRunner, tmp_path: Path
) -> None:
    output = tmp_path / "generated"
    target = output / "src/runtime/telemetry.ts"
    target.parent.mkdir(parents=True)
    target.write_text("// local runtime code\n")
    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            "tests/resources/test_openapi.yaml",
            "--output-dir",
            str(output),
            "--transport",
            "stdio",
        ],
    )
    assert result.exit_code == 0, result.output
    assert target.read_text() == "// local runtime code\n"


def test_policy_accepts_unquoted_off(runner: CliRunner, tmp_path: Path) -> None:
    policy = tmp_path / "mcpgen.yaml"
    policy.write_text("generate:\n  telemetry: off\n")
    output = tmp_path / "out"
    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            "tests/resources/test_openapi.yaml",
            "--output-dir",
            str(output),
            "--config",
            str(policy),
        ],
    )
    assert result.exit_code == 0, result.output
    assert not (output / "src/runtime/telemetry.ts").exists()


def test_enabled_telemetry_rejects_unowned_collision_before_writes(
    runner: CliRunner, tmp_path: Path
) -> None:
    output = tmp_path / "generated"
    target = output / "src/runtime/telemetry.ts"
    target.parent.mkdir(parents=True)
    target.write_text("// custom runtime module\n")
    manifest = output / "package.json"
    manifest.write_text("original manifest\n")
    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            "tests/resources/test_openapi.yaml",
            "--output-dir",
            str(output),
            "--telemetry",
            "opentelemetry",
        ],
    )
    assert result.exit_code != 0
    assert "src/runtime/telemetry.ts" in result.output
    assert "not a generated telemetry module" in result.output
    assert target.read_text() == "// custom runtime module\n"
    assert manifest.read_text() == "original manifest\n"


def test_enabled_telemetry_regenerates_owned_module(
    runner: CliRunner, tmp_path: Path
) -> None:
    output = tmp_path / "generated"
    args = [
        "generate",
        "--openapi-json",
        "tests/resources/test_openapi.yaml",
        "--output-dir",
        str(output),
        "--telemetry",
        "opentelemetry",
    ]
    result = runner.invoke(cli, args)
    assert result.exit_code == 0, result.output
    target = output / "src/runtime/telemetry.ts"
    original = target.read_text()
    target.write_text(original + "\n// generated file modification\n")
    result = runner.invoke(cli, args)
    assert result.exit_code == 0, result.output
    assert target.read_text() == original
