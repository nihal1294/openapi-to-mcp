from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, mock_open

import jinja2
import pytest

from openapi_to_mcp.adapters.generator import Generator
from openapi_to_mcp.common.exceptions import GenerationError
from tests.utils import setup_jinja_mocks, setup_path_mocks


@pytest.fixture
def mock_jinja_env(mocker: Any) -> MagicMock:
    """Mocks the jinja2.Environment class and its methods."""
    mock_env = MagicMock(spec=jinja2.Environment)
    mock_template = MagicMock(spec=jinja2.Template)
    mock_template.render.return_value = "rendered content"
    mock_env.get_template.return_value = mock_template
    mocker.patch(
        "openapi_to_mcp.adapters.generator.jinja2.Environment", return_value=mock_env
    )
    mocker.patch("openapi_to_mcp.adapters.generator.jinja2.FileSystemLoader")
    return mock_env


def test_generator_initialization(mocker: Any) -> None:
    """Test successful initialization and path setup."""
    output_dir = "test/init/output"
    context = {"key": "value"}

    mocks = setup_path_mocks(mocker, output_dir)

    gen = Generator(output_dir=output_dir, context=context)

    assert gen.output_path is mocks["output_path"]
    assert gen.context == context
    assert gen.template_dir is mocks["template_dir"]
    assert gen.env is None
    mocks["path_class"].assert_any_call(output_dir)


def test_generator_setup_environment_success(mocker: Any) -> None:
    """Test successful Jinja2 environment setup."""
    output_dir = "fake/output"
    context = {}

    path_mocks = setup_path_mocks(mocker, output_dir)
    jinja_mocks = setup_jinja_mocks(mocker)

    gen = Generator(output_dir=output_dir, context=context)
    gen._setup_environment()

    path_mocks["template_dir"].is_dir.assert_called_once()
    jinja_mocks["fs_loader"].assert_called_once_with(gen.template_dir)
    jinja_mocks["env_constructor"].assert_called_once()
    assert gen.env is jinja_mocks["env"]


def test_generator_setup_environment_template_dir_not_found(mocker: Any) -> None:
    """Test error when template directory doesn't exist."""
    output_dir = "fake/output"
    context = {}

    path_mocks = setup_path_mocks(mocker, output_dir)
    path_mocks["template_dir"].is_dir.return_value = False

    gen = Generator(output_dir=output_dir, context=context)

    with pytest.raises(GenerationError, match="Template directory not found"):
        gen._setup_environment()

    path_mocks["template_dir"].is_dir.assert_called_once()


@pytest.fixture
def generator_for_render(mocker: Any) -> Generator:
    """Provides a Generator instance with Path mocked for rendering tests."""
    output_dir = "fake/render/output"
    context = {"server_name": "render-test", "tools": []}

    _ = setup_path_mocks(mocker, output_dir)

    gen = Generator(output_dir=output_dir, context=context)

    return gen


def test_generator_ensure_output_directories_success(mocker: Any) -> None:
    """Test successful creation of output directories."""
    output_dir = "fake/output"
    context = {}

    path_mocks = setup_path_mocks(mocker, output_dir)
    mock_src_path = MagicMock(spec=Path, name="src_path")

    path_mocks["output_path"].__truediv__.return_value = mock_src_path

    gen = Generator(output_dir=output_dir, context=context)

    gen._ensure_output_directories()

    path_mocks["output_path"].mkdir.assert_called_once_with(parents=True, exist_ok=True)
    path_mocks["output_path"].__truediv__.assert_called_once_with("src")
    mock_src_path.mkdir.assert_called_once_with(exist_ok=True)


def test_generator_ensure_output_directories_os_error(mocker: Any) -> None:
    """Test error handling during directory creation."""
    output_dir = "fake/output"
    context = {}

    path_mocks = setup_path_mocks(mocker, output_dir)
    path_mocks["output_path"].mkdir.side_effect = OSError("Permission denied")

    gen = Generator(output_dir=output_dir, context=context)

    with pytest.raises(GenerationError, match="Failed to create output directories"):
        gen._ensure_output_directories()

    path_mocks["output_path"].mkdir.assert_called_once_with(parents=True, exist_ok=True)


def test_generator_render_and_write_success(
    mock_jinja_env: MagicMock, generator_for_render: Generator
) -> None:
    """Test successful rendering and writing of a template."""
    gen = generator_for_render
    gen.env = mock_jinja_env
    template_name = "test.j2"

    mock_output_file = MagicMock(spec=Path)
    m_open = mock_open()
    mock_output_file.open = m_open

    gen._render_and_write(template_name, mock_output_file)

    mock_jinja_env.get_template.assert_called_once_with(template_name)
    mock_jinja_env.get_template.return_value.render.assert_called_once_with(gen.context)
    mock_output_file.open.assert_called_once_with("w", encoding="utf-8")
    m_open().write.assert_called_once_with("rendered content")


def test_generator_render_and_write_env_not_init(
    generator_for_render: Generator,
) -> None:
    """Test error if environment is not initialized before rendering."""
    gen = generator_for_render
    gen.env = None

    mock_output_file = MagicMock(spec=Path)
    with pytest.raises(GenerationError, match="Jinja2 environment not initialized"):
        gen._render_and_write("test.j2", mock_output_file)


def test_generator_render_and_write_template_not_found(
    generator_for_render: Generator, mock_jinja_env: MagicMock
) -> None:
    """Test error handling when a template is not found."""
    gen = generator_for_render
    gen.env = mock_jinja_env

    mock_jinja_env.get_template.side_effect = jinja2.TemplateNotFound("missing.j2")

    mock_output_file = MagicMock(spec=Path)
    with pytest.raises(
        GenerationError, match="Required template 'missing.j2' not found"
    ):
        gen._render_and_write("missing.j2", mock_output_file)
    mock_jinja_env.get_template.assert_called_once_with("missing.j2")


def test_generator_render_and_write_write_error(
    generator_for_render: Generator, mock_jinja_env: MagicMock
) -> None:
    """Test error handling when writing the output file fails."""
    gen = generator_for_render
    gen.env = mock_jinja_env
    template_name = "test.j2"

    mock_output_file = MagicMock(spec=Path)
    mock_output_file.open.side_effect = OSError("Disk full")

    with pytest.raises(GenerationError, match="Error rendering or writing template"):
        gen._render_and_write(template_name, mock_output_file)

    mock_jinja_env.get_template.assert_called_once_with(template_name)
    mock_jinja_env.get_template.return_value.render.assert_called_once_with(gen.context)
    mock_output_file.open.assert_called_once_with("w", encoding="utf-8")


def test_generator_generate_files_success(mocker: Any) -> None:
    """Test the main generate_files orchestrator method on success."""
    output_dir = "fake/output"
    context = {"server_name": "test-server", "tools": [], "transport": "stdio"}

    path_mocks = setup_path_mocks(mocker, output_dir)

    def path_side_effect(arg):
        if arg == output_dir:
            return path_mocks["output_path"]
        if arg == __file__ or (isinstance(arg, str) and "generator.py" in arg):
            return path_mocks["file_path"]
        return MagicMock(spec=Path)

    path_mocks["path_class"].side_effect = path_side_effect

    mock_parent_parent = MagicMock(spec=Path, name="mock_parent_parent")
    path_mocks["file_path"].parent.parent = mock_parent_parent
    mock_parent_parent.__truediv__.return_value = path_mocks["template_dir"]

    gen = Generator(output_dir=output_dir, context=context)

    mock_env = MagicMock(spec=jinja2.Environment)
    mocker.patch.object(
        gen, "_setup_environment", side_effect=lambda: setattr(gen, "env", mock_env)
    )
    mocker.patch.object(gen, "_ensure_output_directories")
    mock_render = mocker.patch.object(gen, "_render_and_write")

    mock_src_path = MagicMock(spec=Path, name="src_path")
    output_files = {
        "src": mock_src_path,
        "package.json": MagicMock(spec=Path, name="pkg_json"),
        "tsconfig.json": MagicMock(spec=Path, name="tsconfig"),
        "README.md": MagicMock(spec=Path, name="readme"),
        ".env.example": MagicMock(spec=Path, name="env_example"),
        "src/index.ts": MagicMock(spec=Path, name="index_ts"),
        "src/server.ts": MagicMock(spec=Path, name="server_ts"),
        "src/transport.ts": MagicMock(spec=Path, name="transport_ts"),
    }

    def output_truediv_side_effect(arg):
        return output_files.get(arg, MagicMock(spec=Path))

    def src_truediv_side_effect(arg):
        key = f"src/{arg}"
        return output_files.get(key, MagicMock(spec=Path))

    gen.output_path.__truediv__.side_effect = output_truediv_side_effect
    mock_src_path.__truediv__.side_effect = src_truediv_side_effect

    gen.generate_files()

    gen._setup_environment.assert_called_once()
    gen._ensure_output_directories.assert_called_once()

    expected_calls = [
        call("package.json.j2", output_files["package.json"]),
        call("tsconfig.json.j2", output_files["tsconfig.json"]),
        call("src/server.ts.j2", output_files["src/server.ts"]),
        call("README.md.j2", output_files["README.md"]),
        call(".env.example.j2", output_files[".env.example"]),
        call("src/index.ts.j2", output_files["src/index.ts"]),
        call("src/transport_stdio.ts.j2", output_files["src/transport.ts"]),
    ]

    assert mock_render.call_count == len(expected_calls)
    mock_render.assert_has_calls(expected_calls, any_order=True)
