from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from openapi_to_mcp.cli import cli
from openapi_to_mcp.common.exceptions import NoToolsMappedError

if TYPE_CHECKING:
    from pathlib import Path
    from unittest.mock import MagicMock

    from openapi_to_mcp.commands.generation_models import GenerationRequest


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _assert_generation_request(
    request: GenerationRequest, source: Path, output: Path
) -> None:
    assert request.source == str(source)
    assert request.output_dir == str(output)
    assert request.settings.identity.name == "Pet MCP"
    assert request.settings.identity.version == "2.0.0"
    assert request.settings.transport.kind == "streamable-http"
    assert request.settings.transport.host == "127.0.0.2"
    assert request.settings.transport.port == 9090
    assert request.settings.transport.endpoint == "/tools"
    assert request.settings.behavior.tool_grouping == "tag-prefix"
    assert request.settings.behavior.strict is False
    assert request.settings.behavior.runtime_validation == "none"
    assert request.settings.behavior.on_mapping_error == "fail"
    assert request.settings.behavior.on_schema_error == "skip"


def test_generate_handles_no_tools_mapped_cleanly(
    runner: CliRunner, tmp_path: Path, mocker: MagicMock
) -> None:
    mocker.patch(
        "openapi_to_mcp.commands.generate.generate_project",
        side_effect=NoToolsMappedError("No tools were mapped from the OpenAPI spec."),
    )

    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            str(tmp_path / "openapi.yaml"),
            "--output-dir",
            str(tmp_path / "generated"),
        ],
    )

    assert result.exit_code == 0
    assert "No tools were mapped from the OpenAPI spec." in result.output
    assert "Traceback" not in result.output


def test_generate_composes_single_generation_request(
    runner: CliRunner, tmp_path: Path, mocker: MagicMock
) -> None:
    captured: list[GenerationRequest] = []

    def capture_request(request: GenerationRequest) -> None:
        captured.append(request)

    mocker.patch(
        "openapi_to_mcp.commands.generate.generate_project",
        side_effect=capture_request,
    )
    source = tmp_path / "openapi.yaml"
    output = tmp_path / "generated"

    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            str(source),
            "--output-dir",
            str(output),
            "--mcp-server-name",
            "Pet MCP",
            "--mcp-server-version",
            "2.0.0",
            "--tool-grouping",
            "tag-prefix",
            "--transport",
            "streamable-http",
            "--host",
            "127.0.0.2",
            "--port",
            "9090",
            "--mcp-endpoint",
            "/tools",
            "--no-strict",
            "--runtime-validation",
            "none",
            "--on-mapping-error",
            "fail",
            "--on-schema-error",
            "skip",
        ],
    )

    assert result.exit_code == 0
    assert len(captured) == 1
    _assert_generation_request(captured[0], source, output)
