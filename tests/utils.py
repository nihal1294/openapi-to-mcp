from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from click.testing import CliRunner, Result

from openapi_to_mcp.cli import cli
from tests.constants import VALID_OPENAPI_YAML


def setup_path_mocks(mocker: Any, output_dir: str) -> dict[str, MagicMock]:
    """
    Set up Path mocks for generator tests with proper parent chain.

    This handles the complex patching of Path(__file__).parent.parent / "templates"
    which is commonly used in tests.

    Args:
        mocker: pytest-mock fixture
        output_dir: Directory path to mock as output

    Returns:
        Dictionary containing all mock objects
    """
    mock_path_class = mocker.patch("openapi_to_mcp.adapters.generator.Path")
    mock_output_path = MagicMock(spec=Path, name="output_path")
    mock_file_path = MagicMock(spec=Path, name="file_path")
    mock_parent = MagicMock(spec=Path, name="parent")
    mock_parent_parent = MagicMock(spec=Path, name="parent_parent")
    mock_template_dir = MagicMock(spec=Path, name="template_dir")

    def path_side_effect(arg):
        if arg == output_dir:
            return mock_output_path
        if arg == __file__ or (isinstance(arg, str) and "generator.py" in arg):
            return mock_file_path
        return MagicMock(spec=Path)

    mock_path_class.side_effect = path_side_effect

    mock_file_path.parent = mock_parent
    mock_parent.parent = mock_parent_parent
    mock_parent_parent.__truediv__.return_value = mock_template_dir

    mock_template_dir.is_dir.return_value = True

    return {
        "path_class": mock_path_class,
        "output_path": mock_output_path,
        "file_path": mock_file_path,
        "parent": mock_parent,
        "parent_parent": mock_parent_parent,
        "template_dir": mock_template_dir,
    }


def setup_jinja_mocks(mocker: Any) -> dict[str, MagicMock]:
    """
    Set up common Jinja2 mocks for template rendering tests.

    Args:
        mocker: pytest-mock fixture

    Returns:
        Dictionary containing Jinja2 mock objects
    """
    mock_env = MagicMock(name="jinja_env")
    mock_template = MagicMock(name="jinja_template")
    mock_template.render.return_value = "rendered content"
    mock_env.get_template.return_value = mock_template

    mock_fs_loader = mocker.patch(
        "openapi_to_mcp.adapters.generator.jinja2.FileSystemLoader"
    )
    mock_env_constructor = mocker.patch(
        "openapi_to_mcp.adapters.generator.jinja2.Environment", return_value=mock_env
    )

    return {
        "env": mock_env,
        "template": mock_template,
        "fs_loader": mock_fs_loader,
        "env_constructor": mock_env_constructor,
    }


def setup_cli_test_file(tmp_path: Path, content: str = VALID_OPENAPI_YAML) -> Path:
    """
    Create a temporary OpenAPI file for CLI testing.

    Args:
        tmp_path: pytest temporary path
        content: YAML content to write to file

    Returns:
        Path to created OpenAPI file
    """
    openapi_file = tmp_path / "openapi.yaml"
    with openapi_file.open("w") as f:
        f.write(content)
    return openapi_file


def invoke_cli_generate(
    runner: CliRunner,
    openapi_file: Path,
    output_dir: str = "./output",
    transport: str = "stdio",
    server_name: str | None = None,
) -> Result:
    """
    Invoke the CLI generate command with standard options.

    Args:
        runner: Click test runner
        openapi_file: Path to OpenAPI file
        output_dir: Output directory path
        transport: Transport type (stdio or sse)
        server_name: Optional MCP server name

    Returns:
        Click CLI Result
    """
    args = [
        "generate",
        "--openapi-json",
        str(openapi_file),
        "--output-dir",
        output_dir,
        "--transport",
        transport,
    ]

    if server_name:
        args.extend(["--mcp-server-name", server_name])

    return runner.invoke(cli, args)


def assert_error_of_type(caplog: Any, error_type: type, error_message: str) -> None:
    """
    Assert that logs contain an error of the specified type and message.

    Args:
        caplog: pytest caplog fixture
        error_type: Type of error to find
        error_message: Message to search for
    """
    error_logs = [
        rec
        for rec in caplog.records
        if rec.levelname == "ERROR"
        and rec.exc_info
        and isinstance(rec.exc_info[1], error_type)
    ]
    assert len(error_logs) >= 1, f"No {error_type.__name__} found in logs"
    assert error_message in str(error_logs[0].exc_info[1])
