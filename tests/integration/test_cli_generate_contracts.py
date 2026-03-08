from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from openapi_to_mcp.cli import cli


def _normalize_output(text: str) -> str:
    return " ".join(re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text).split())


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_generate_prefills_swagger2_base_url(runner: CliRunner, tmp_path: Path) -> None:
    spec_path = tmp_path / "swagger2.json"
    spec_path.write_text(
        json.dumps(
            {
                "swagger": "2.0",
                "info": {"title": "Swagger Two", "version": "1.2.3"},
                "schemes": ["https"],
                "host": "api.example.com",
                "basePath": "/v1",
                "paths": {
                    "/ping": {"get": {"responses": {"200": {"description": "OK"}}}}
                },
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "generated"

    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            str(spec_path),
            "--output-dir",
            str(output_dir),
            "--transport",
            "stdio",
        ],
    )

    assert result.exit_code == 0
    env_example = (output_dir / ".env.example").read_text(encoding="utf-8")
    assert "TARGET_API_BASE_URL=https://api.example.com/v1" in env_example


def test_generate_rejects_invalid_streamable_endpoint_cleanly(
    runner: CliRunner, tmp_path: Path
) -> None:
    spec_path = Path(__file__).resolve().parents[1] / "resources" / "test_openapi.yaml"
    output_dir = tmp_path / "generated"

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
            "--mcp-endpoint",
            "mcp",
        ],
    )

    assert result.exit_code != 0
    assert "--mcp-endpoint must start with '/'" in _normalize_output(result.output)
    assert "Traceback" not in result.output
    assert not (output_dir / "generation_report.json").exists()
