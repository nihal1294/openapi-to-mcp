from __future__ import annotations

import json
from typing import TYPE_CHECKING

from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner


def _write_xquik_read_spec(path: Path) -> Path:
    spec = {
        "openapi": "3.1.0",
        "info": {"title": "Xquik Read API", "version": "1.0.0"},
        "servers": [{"url": "https://xquik.com"}],
        "paths": {
            "/api/v1/x/tweets/search": {
                "get": {
                    "operationId": "searchTweets",
                    "summary": (
                        "Search tweets by query, Tweet ID, X status URL, "
                        "or account date window"
                    ),
                    "security": [{"apiKey": []}, {"oauthBearer": []}],
                    "parameters": [
                        {
                            "name": "q",
                            "in": "query",
                            "required": True,
                            "schema": {"type": "string"},
                            "description": "Search query.",
                        },
                        {
                            "name": "queryType",
                            "in": "query",
                            "required": False,
                            "schema": {
                                "type": "string",
                                "enum": ["Latest", "Top"],
                                "default": "Latest",
                            },
                            "description": "Sort order.",
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Paginated tweets.",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/PaginatedTweets"
                                    }
                                }
                            },
                        }
                    },
                }
            }
        },
        "components": {
            "securitySchemes": {
                "apiKey": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "x-api-key",
                },
                "oauthBearer": {"type": "http", "scheme": "bearer"},
            },
            "schemas": {
                "PaginatedTweets": {
                    "type": "object",
                    "required": ["tweets", "has_next_page", "next_cursor"],
                    "properties": {
                        "tweets": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/SearchTweet"},
                        },
                        "has_next_page": {"type": "boolean"},
                        "next_cursor": {"type": "string"},
                    },
                },
                "SearchTweet": {
                    "type": "object",
                    "required": ["id", "text"],
                    "properties": {
                        "id": {"type": "string"},
                        "text": {"type": "string"},
                        "url": {"type": "string"},
                    },
                },
            },
        },
    }
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path


def test_generate_handles_xquik_read_api_contract(
    runner: CliRunner, tmp_path: Path
) -> None:
    spec_path = _write_xquik_read_spec(tmp_path / "xquik-read-api.json")
    output_dir = tmp_path / "generated-xquik-read-api"

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
    env_example = (output_dir / ".env.example").read_text(encoding="utf-8")
    generated_source = (output_dir / "src" / "runtime" / "generated.ts").read_text(
        encoding="utf-8"
    )

    assert "TARGET_API_BASE_URL=https://xquik.com" in env_example
    assert "AUTH_APIKEY_API_KEY=" in env_example
    assert "AUTH_OAUTHBEARER_TOKEN=" in env_example
    assert '"name": "searchTweets"' in generated_source
    assert '"queryType"' in generated_source
    assert '"Latest"' in generated_source
    assert '"Top"' in generated_source
    assert '"outputSchema": {' in generated_source
    assert '"has_next_page"' in generated_source
    assert '"x-api-key"' in generated_source
    assert '"scheme": "bearer"' in generated_source
