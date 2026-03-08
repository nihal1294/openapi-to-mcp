from __future__ import annotations

import json
from typing import TYPE_CHECKING

from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner


def _write_output_schema_spec(path: Path) -> Path:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Output Schema API", "version": "1.0.0"},
        "servers": [{"url": "https://example.com/api"}],
        "paths": {
            "/items": {
                "get": {
                    "operationId": "listItems",
                    "responses": {
                        "200": {
                            "description": "OK",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "items": {
                                                "type": "array",
                                                "items": {"type": "string"},
                                            }
                                        },
                                        "required": ["items"],
                                    }
                                }
                            },
                        }
                    },
                }
            }
        },
    }
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path


def test_generate_emits_output_schema_and_structured_result_helper(
    runner: CliRunner, tmp_path: Path
) -> None:
    spec_path = _write_output_schema_spec(tmp_path / "output-schema.json")
    output_dir = tmp_path / "generated-output-schema"

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
    server_source = (output_dir / "src" / "server.ts").read_text(encoding="utf-8")
    assert '"outputSchema": {' in server_source
    assert "function buildToolSuccessResult(" in server_source
    assert "structuredContent: responseData" in server_source
