from __future__ import annotations

from typing import TYPE_CHECKING

from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner, Result


def _generate_project(runner: CliRunner, output_dir: Path) -> Result:
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
        ],
    )


def test_generate_emits_preserved_custom_boundary(
    runner: CliRunner, tmp_path: Path
) -> None:
    output_dir = tmp_path / "generated-custom"

    result = _generate_project(runner, output_dir)

    assert result.exit_code == 0
    custom_tools = output_dir / "src" / "custom" / "tools.ts"
    server_source = (output_dir / "src" / "server.ts").read_text(encoding="utf-8")
    runtime_source = (output_dir / "src" / "runtime" / "generated.ts").read_text(
        encoding="utf-8"
    )
    custom_source = custom_tools.read_text(encoding="utf-8")
    assert custom_tools.exists()
    assert "export interface CustomToolDefinition" in runtime_source
    assert "import type { CustomToolDefinition } from '../runtime/generated.js';" in (
        custom_source
    )
    assert "export function getCustomTools()" in custom_source
    assert "getCustomTools" in server_source
    assert (
        "type CustomToolDefinition,\n  toolRuntimeMap,\n  tools,\n} from './runtime/generated.js';"
        in (server_source)
    )
    assert (
        "type CustomToolDefinition,\n} from './custom/tools.js';" not in server_source
    )
    assert "from './custom/tools.js';" in server_source


def test_generate_preserves_existing_custom_tools_file(
    runner: CliRunner, tmp_path: Path
) -> None:
    output_dir = tmp_path / "generated-custom"

    first_result = _generate_project(runner, output_dir)
    assert first_result.exit_code == 0

    custom_tools = output_dir / "src" / "custom" / "tools.ts"
    preserved_content = """export function getCustomTools() {\n  return [];\n}\n"""
    custom_tools.write_text(preserved_content, encoding="utf-8")

    second_result = _generate_project(runner, output_dir)

    assert second_result.exit_code == 0
    assert custom_tools.read_text(encoding="utf-8") == preserved_content
