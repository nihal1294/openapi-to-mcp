"""CLI policy errors remain fatal during compatibility checks."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
import yaml

from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner


@pytest.mark.parametrize("document_type", ["swagger", "openapi"])
@pytest.mark.parametrize("strict", [False, True])
def test_invalid_execution_policy_fails_generation(
    runner: CliRunner,
    tmp_path: Path,
    *,
    document_type: str,
    strict: bool,
) -> None:
    spec_path = tmp_path / f"{document_type}.json"
    policy_path = tmp_path / "mcpgen.yaml"
    output_dir = tmp_path / "output"
    spec_path.write_text(json.dumps(_spec(document_type)), encoding="utf-8")
    policy_path.write_text(yaml.safe_dump(_policy()), encoding="utf-8")

    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            str(spec_path),
            "--config",
            str(policy_path),
            "--output-dir",
            str(output_dir),
            "--strict" if strict else "--no-strict",
        ],
    )

    assert result.exit_code != 0
    assert "cache_ttl_ms" in result.output
    assert "safe HTTP method" in result.output
    assert not (output_dir / "generation_report.json").exists()


def _policy() -> dict[str, object]:
    return {
        "auth": {"operations": {"POST /secure": {"security": []}}},
        "execution": {"operations": {"POST /secure": {"cache_ttl_ms": 1000}}},
    }


def _spec(document_type: str) -> dict[str, object]:
    paths = {
        "/secure": {"post": {"responses": {"200": {"description": "OK"}}}},
        "/public": {
            "get": {
                "security": [],
                "responses": {"200": {"description": "OK"}},
            }
        },
    }
    document = {
        "info": {"title": "Policy error", "version": "1.0.0"},
        "security": [{"Legacy": []}],
        "paths": paths,
    }
    if document_type == "swagger":
        document.update(
            {
                "swagger": "2.0",
                "host": "api.example.com",
                "securityDefinitions": {
                    "Legacy": {
                        "type": "apiKey",
                        "in": "header",
                        "name": "X-Key",
                    }
                },
            }
        )
    else:
        document.update(
            {
                "openapi": "3.0.0",
                "servers": [{"url": "https://api.example.com"}],
                "components": {
                    "securitySchemes": {
                        "Legacy": {
                            "type": "apiKey",
                            "in": "header",
                            "name": "X-Key",
                        }
                    }
                },
            }
        )
    return document
