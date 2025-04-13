import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from openapi_to_mcp.adapters.generator import Generator
from tests.constants import VALID_MCP_TOOL, VALID_OPENAPI_SPEC
from tests.utils import setup_jinja_mocks, setup_path_mocks


@pytest.fixture
def runner() -> CliRunner:
    """Provides a CliRunner instance for CLI tests."""
    return CliRunner()


@pytest.fixture
def cli_test_context(runner: CliRunner, tmp_path: Path, caplog: Any) -> dict:
    """
    Provides a context dictionary for CLI testing.

    Returns:
        Dictionary containing common CLI test objects:
        - runner: CliRunner instance
        - tmp_path: Temporary directory path
        - caplog: Logging capture fixture
    """
    caplog.set_level(logging.ERROR)
    return {"runner": runner, "tmp_path": tmp_path, "caplog": caplog}


@pytest.fixture
def mock_spec_loader(mocker: Any) -> MagicMock:
    """Mocks the SpecLoader class."""
    mock = mocker.patch("openapi_to_mcp.adapters.spec_loader.SpecLoader", autospec=True)
    mock.return_value.load_and_validate.return_value = VALID_OPENAPI_SPEC
    return mock


@pytest.fixture
def mock_mapper(mocker: Any) -> MagicMock:
    """Mocks the Mapper class."""
    mock = mocker.patch("openapi_to_mcp.mapping.Mapper", autospec=True)
    mock.return_value.map_tools.return_value = [VALID_MCP_TOOL]
    return mock


@pytest.fixture
def mock_generator(mocker: Any) -> MagicMock:
    """Mocks the Generator class."""
    mock = mocker.patch("openapi_to_mcp.adapters.generator.Generator", autospec=True)
    mock.return_value.generate_files.return_value = None
    return mock


@pytest.fixture
def mock_jinja_env(mocker: Any) -> MagicMock:
    """Mocks the jinja2.Environment class and its methods."""
    jinja_mocks = setup_jinja_mocks(mocker)
    return jinja_mocks["env"]


@pytest.fixture
def generator_test_output_dir() -> str:
    """Returns a standard output directory path for Generator tests."""
    return "fake/output/dir"


@pytest.fixture
def generator_test_context(mocker: Any, generator_test_output_dir: str) -> dict:
    """Provides a standard test context for Generator."""
    return {
        "server_name": "test-server",
        "server_version": "1.0.0",
        "transport": "stdio",
        "tools": [VALID_MCP_TOOL],
    }


@pytest.fixture
def generator_with_mocks(
    mocker: Any, generator_test_output_dir: str, generator_test_context: dict
) -> tuple[Generator, dict]:
    """
    Creates a Generator instance with all necessary mocks set up.

    Returns:
        Tuple containing:
        - The Generator instance
        - Dictionary of all mock objects used
    """
    output_dir = generator_test_output_dir
    context = generator_test_context

    path_mocks = setup_path_mocks(mocker, output_dir)

    gen = Generator(output_dir=output_dir, context=context)

    return gen, path_mocks


@pytest.fixture
def generator_with_template_dir(
    mocker: Any, generator_with_mocks: tuple[Generator, dict]
) -> Generator:
    """Provides a Generator with template_dir properly set up for tests that need it."""
    gen, mocks = generator_with_mocks

    if hasattr(gen, "template_dir"):
        gen.template_dir = mocks["template_dir"]

    return gen
