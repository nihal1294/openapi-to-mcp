from __future__ import annotations

import json
from typing import TYPE_CHECKING

from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner


def _write_tool_shaping_spec(path: Path) -> Path:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Tool Shaping", "version": "1.0.0"},
        "servers": [{"url": "https://example.com/api"}],
        "components": {
            "examples": {
                "SearchBody": {"value": {"query": "wireless", "limit": 5}},
            }
        },
        "paths": {
            "/inventory/search/{inventoryId}": {
                "post": {
                    "operationId": "searchInventory",
                    "parameters": [
                        {
                            "name": "inventoryId",
                            "in": "path",
                            "required": True,
                            "example": "inv_123",
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "status",
                            "in": "query",
                            "example": None,
                            "schema": {"type": "string", "nullable": True},
                        },
                    ],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "examples": {
                                    "search": {
                                        "$ref": "#/components/examples/SearchBody"
                                    }
                                },
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "query": {"type": "string"},
                                        "limit": {"type": "integer", "default": 10},
                                    },
                                },
                            }
                        }
                    },
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path


def test_generate_emits_shaped_descriptions_and_input_examples(
    runner: CliRunner, tmp_path: Path
) -> None:
    spec_path = _write_tool_shaping_spec(tmp_path / "tool-shaping.json")
    output_dir = tmp_path / "generated-tool-shaping"

    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            str(spec_path),
            "--output-dir",
            str(output_dir),
            "--transport",
            "streamable-http",
        ],
    )

    assert result.exit_code == 0
    generated_source = (output_dir / "src" / "runtime" / "generated.ts").read_text(
        encoding="utf-8"
    )
    assert '"description": "Search inventory."' in generated_source
    assert '"examples": [' in generated_source
    assert '"inventoryId": "inv_123"' in generated_source
    assert '"status": null' in generated_source
    assert '"query": "wireless"' in generated_source
