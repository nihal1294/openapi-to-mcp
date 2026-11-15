"""Validate generated client-facing metadata against the installed MCP SDK."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import TYPE_CHECKING

from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner


def test_compiled_generated_annotations_match_sdk(
    runner: CliRunner, tmp_path: Path
) -> None:
    spec = {
        "openapi": "3.1.0",
        "info": {"title": "Annotations", "version": "1.0.0"},
        "paths": {
            "/items": {
                "get": {
                    "operationId": "items",
                    "tags": ["Pets"],
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    output = tmp_path / "server"
    args = [
        "generate",
        "--openapi-json",
        str(spec_path),
        "--output-dir",
        str(output),
        "--tool-grouping",
        "tag-prefix",
    ]
    assert runner.invoke(cli, args).exit_code == 0
    custom = output / "src/custom/tools.ts"
    custom_source = """import type { CustomToolDefinition } from '../runtime/generated.js';
export function getCustomTools(): CustomToolDefinition[] {
  return [{ tool: { name: 'custom', inputSchema: { type: 'object' }, annotations: { openWorldHint: false } }, handler: async () => ({ content: [] }) }];
}
"""
    custom.write_text(custom_source, encoding="utf-8")
    assert runner.invoke(cli, args).exit_code == 0
    assert custom.read_text(encoding="utf-8") == custom_source
    npm = shutil.which("npm")
    node = shutil.which("node")
    assert npm
    assert node
    for command in (
        [npm, "install", "--ignore-scripts", "--no-audit", "--no-fund"],
        [npm, "run", "build"],
    ):
        result = subprocess.run(  # noqa: S603
            command,
            cwd=output,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    script = """
import { ListToolsResultSchema } from '@modelcontextprotocol/core';
import { tools, toolRuntimeData } from './build/runtime/generated.js';
import { getCustomTools } from './build/custom/tools.js';
const result = ListToolsResultSchema.parse({ tools });
if (result.tools[0].name !== 'pets_items' || JSON.stringify(result.tools[0].annotations) !== JSON.stringify({ readOnlyHint: true, destructiveHint: false, idempotentHint: true })) throw Error('Unexpected annotations');
if ('annotations' in toolRuntimeData.pets_items) throw Error('Runtime data contains annotations');
const custom = ListToolsResultSchema.parse({ tools: getCustomTools().map(entry => entry.tool) });
if (custom.tools[0].annotations.openWorldHint !== false) throw Error('Custom metadata changed');
"""
    result = subprocess.run(  # noqa: S603
        [node, "--input-type=module", "--eval", script],
        cwd=output,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
