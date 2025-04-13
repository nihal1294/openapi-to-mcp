import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner, Result

from openapi_to_mcp.cli import cli
from openapi_to_mcp.common.exceptions import (
    GenerationError,
    MappingError,
    SpecLoaderError,
)
from tests.constants import VALID_MCP_TOOL, VALID_OPENAPI_SPEC
from tests.utils import assert_error_of_type, invoke_cli_generate, setup_cli_test_file


@pytest.fixture
def runner() -> CliRunner:
    """Provides a CliRunner instance."""
    return CliRunner()


@pytest.fixture
def mock_spec_loader(mocker: Any) -> MagicMock:
    """Mocks the SpecLoader class."""
    mock = mocker.patch("openapi_to_mcp.adapters.spec_loader.SpecLoader", autospec=True)
    mock.return_value.load_and_validate.return_value = {
        "openapi": "3.0.0",
        "info": {"title": "Mock Spec", "version": "1.0"},
        "paths": {"/test": {"get": {"summary": "Test GET"}}},
        "servers": [{"url": "http://mock.api"}],
    }
    return mock


@pytest.fixture
def mock_mapper(mocker: Any) -> MagicMock:
    """Mocks the Mapper class."""
    mock = mocker.patch("openapi_to_mcp.mapping.Mapper", autospec=True)
    mock.return_value.map_tools.return_value = [
        {
            "name": "get_test",
            "description": "Test GET",
            "inputSchema": {},
            "_original_method": "GET",
            "_original_path": "/test",
            "_original_parameters": [],
            "_original_request_body": None,
        }
    ]
    return mock


@pytest.fixture
def mock_generator(mocker: Any) -> MagicMock:
    """Mocks the Generator class."""
    mock = mocker.patch("openapi_to_mcp.adapters.generator.Generator", autospec=True)
    mock.return_value.generate_files.return_value = None
    return mock


def test_cli_success_default_args(
    runner: CliRunner,
    caplog: Any,
) -> None:
    """Test successful CLI execution with default output directory."""
    caplog.set_level(logging.INFO)
    openapi_file = "tests/resources/test_openapi.yaml"
    output_dir = "./mcp-server"

    result: Result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            openapi_file,
            "--output-dir",
            output_dir,
            "--mcp-server-name",
            "mcp-server",
            "--transport",
            "stdio",
        ],
    )

    if result.exception:
        import traceback

        traceback.print_exception(
            type(result.exception), result.exception, result.exc_info[2]
        )

    assert result.exit_code == 0
    assert "Starting MCP server generation..." in caplog.text
    assert "Loading OpenAPI spec from:" in caplog.text
    assert "OpenAPI spec loaded and validated successfully." in caplog.text
    assert "Mapping OpenAPI paths to MCP tools..." in caplog.text
    assert "Mapped 1 tools." in caplog.text
    assert f"Generating files in: {output_dir}" in caplog.text
    assert "File generation complete." in caplog.text
    assert "MCP server generation successful." in caplog.text
    assert "Please check the README" in result.output
    assert f"{output_dir}" in result.output


def test_cli_success_custom_args(
    runner: CliRunner,
    tmp_path: Path,
    caplog: Any,
) -> None:
    """Test successful CLI execution with custom arguments."""
    caplog.set_level(logging.INFO)
    openapi_file = "tests/resources/test_openapi.json"
    output_dir = tmp_path / "custom-output"
    server_name = "my-custom-server"
    server_version = "2.1.0"
    transport = "sse"
    port = "9090"

    result: Result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            str(openapi_file),
            "--output-dir",
            str(output_dir),
            "--mcp-server-name",
            server_name,
            "--mcp-server-version",
            server_version,
            "--transport",
            transport,
            "--port",
            port,
        ],
    )

    assert result.exit_code == 0
    assert f"Generating files in: {output_dir}" in caplog.text
    assert "MCP server generation successful." in caplog.text
    assert f"{output_dir}" in result.output


def test_cli_missing_openapi_json(cli_test_context: dict) -> None:
    """Test CLI failure when required --openapi-json is missing."""
    result = cli_test_context["runner"].invoke(cli, ["generate"])
    assert result.exit_code != 0
    assert "Missing option '--openapi-json'" in result.output


def test_cli_openapi_file_not_found(cli_test_context: dict) -> None:
    """Test CLI failure when --openapi-json file doesn't exist."""
    non_existent_file = cli_test_context["tmp_path"] / "ghost.yaml"
    result = invoke_cli_generate(cli_test_context["runner"], non_existent_file)
    assert result.exit_code != 0


def test_cli_spec_loader_error(
    cli_test_context: dict,
    mocker: Any,
) -> None:
    """Test CLI failure when SpecLoader raises an error."""
    openapi_file = setup_cli_test_file(cli_test_context["tmp_path"])

    mock_spec_loader = mocker.patch(
        "openapi_to_mcp.commands.generate.SpecLoader", autospec=True
    )
    error_message = "Parsed specification is not a valid dictionary structure."
    mock_spec_loader.return_value.load_and_validate.side_effect = SpecLoaderError(
        error_message
    )

    result = invoke_cli_generate(cli_test_context["runner"], openapi_file)
    assert result.exit_code != 0
    assert_error_of_type(cli_test_context["caplog"], SpecLoaderError, error_message)


def test_cli_mapper_error(
    cli_test_context: dict,
    mocker: Any,
) -> None:
    """Test CLI failure when Mapper raises an error."""
    openapi_file = setup_cli_test_file(cli_test_context["tmp_path"])

    mock_spec_loader = mocker.patch(
        "openapi_to_mcp.commands.generate.SpecLoader", autospec=True
    )
    mock_spec_loader.return_value.load_and_validate.return_value = VALID_OPENAPI_SPEC

    mock_mapper = mocker.patch("openapi_to_mcp.commands.generate.Mapper", autospec=True)
    mock_mapper.return_value.map_tools.side_effect = MappingError("Cannot map paths")

    result = invoke_cli_generate(cli_test_context["runner"], openapi_file)

    assert result.exit_code != 0
    assert_error_of_type(cli_test_context["caplog"], MappingError, "Cannot map paths")


def test_cli_generator_error(
    cli_test_context: dict,
    mocker: Any,
) -> None:
    """Test CLI failure when Generator raises an error."""
    openapi_file = setup_cli_test_file(cli_test_context["tmp_path"])

    mock_spec_loader = mocker.patch(
        "openapi_to_mcp.commands.generate.SpecLoader", autospec=True
    )
    mock_spec_loader.return_value.load_and_validate.return_value = VALID_OPENAPI_SPEC

    mock_mapper = mocker.patch("openapi_to_mcp.commands.generate.Mapper", autospec=True)
    mock_mapper.return_value.map_tools.return_value = [VALID_MCP_TOOL]

    mock_generator = mocker.patch(
        "openapi_to_mcp.commands.generate.Generator", autospec=True
    )
    mock_generator.return_value.generate_files.side_effect = GenerationError(
        "Cannot write files"
    )

    result = invoke_cli_generate(cli_test_context["runner"], openapi_file)

    assert result.exit_code != 0
    assert_error_of_type(
        cli_test_context["caplog"], GenerationError, "Cannot write files"
    )


def test_cli_help_message(runner: CliRunner) -> None:
    """Test that the --help option works."""
    result: Result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Usage: cli [OPTIONS] COMMAND [ARGS]..." in result.output
    assert "generate" in result.output
    assert "test-server" in result.output
