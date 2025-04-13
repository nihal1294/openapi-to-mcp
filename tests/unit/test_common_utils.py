import json
from unittest.mock import mock_open, patch

import pytest

from openapi_to_mcp.common.utils import _parse_dotenv, parse_env_source


def test_parse_dotenv_with_valid_content() -> None:
    """Test parsing a valid .env file."""
    env_content = """
    # Comment line
    KEY1=value1
    KEY2="value2"
    KEY3='value3'
    # Another comment
    KEY4=value with spaces

    # Empty line above
    """

    with patch("builtins.open", mock_open(read_data=env_content)):
        result = _parse_dotenv("fake_path/.env")

    assert result == {
        "KEY1": "value1",
        "KEY2": "value2",
        "KEY3": "value3",
        "KEY4": "value with spaces",
    }


def test_parse_dotenv_with_invalid_format() -> None:
    """Test parsing a .env file with lines that don't have '='."""
    env_content = """
    KEY1=value1
    INVALID_LINE
    KEY2=value2
    """

    with patch("builtins.open", mock_open(read_data=env_content)):
        result = _parse_dotenv("fake_path/.env")

    assert result == {
        "KEY1": "value1",
        "KEY2": "value2",
    }


def test_parse_dotenv_file_not_found() -> None:
    """Test behavior when .env file is not found."""
    with (
        patch("builtins.open", side_effect=FileNotFoundError),
        pytest.raises(ValueError, match=".env file not found at:"),
    ):
        _parse_dotenv("non_existent_file.env")


def test_parse_dotenv_other_error() -> None:
    """Test behavior when another error occurs while parsing the .env file."""
    with (
        patch("builtins.open", side_effect=PermissionError("Permission denied")),
        pytest.raises(ValueError, match="Failed to parse .env file"),
    ):
        _parse_dotenv("fake_path/.env")


def test_parse_env_source_none() -> None:
    """Test parse_env_source with None input."""
    assert parse_env_source(None) is None


def test_parse_env_source_valid_json_string() -> None:
    """Test parse_env_source with a valid JSON string."""
    json_str = '{"KEY1": "value1", "KEY2": "value2"}'
    result = parse_env_source(json_str)

    assert result == {"KEY1": "value1", "KEY2": "value2"}


def test_parse_env_source_invalid_json_string() -> None:
    """Test parse_env_source with invalid JSON string but valid file path."""
    invalid_json = "{not valid json}"

    with (
        patch("os.path.exists", return_value=True),
        patch(
            "openapi_to_mcp.common.utils._parse_dotenv", return_value={"KEY1": "value1"}
        ),
    ):
        result = parse_env_source(invalid_json)

    assert result == {"KEY1": "value1"}


def test_parse_env_source_json_file() -> None:
    """Test parse_env_source with a JSON file path."""
    with (
        patch("os.path.exists", return_value=True),
        patch("builtins.open", mock_open()),
        patch("json.load", return_value={"KEY1": "value1", "KEY2": 2}),
    ):
        result = parse_env_source("config.json")

    assert result == {"KEY1": "value1", "KEY2": "2"}


def test_parse_env_source_env_file() -> None:
    """Test parse_env_source with a .env file path."""
    env_content = """
    KEY1=value1
    KEY2=value2
    """

    with (
        patch("os.path.exists", return_value=True),
        patch("builtins.open", mock_open(read_data=env_content)),
    ):
        result = parse_env_source("config.env")

    assert result == {"KEY1": "value1", "KEY2": "value2"}


def test_parse_env_source_file_not_found() -> None:
    """Test parse_env_source with a non-existent file."""
    with (
        patch("os.path.exists", return_value=False),
        pytest.raises(ValueError, match="File not found"),
    ):
        parse_env_source("non_existent_file.json")


def test_parse_env_source_invalid_json_content() -> None:
    """Test parse_env_source with a JSON file containing non-object content."""
    with (
        patch("os.path.exists", return_value=True),
        patch("builtins.open", mock_open()),
        patch("json.load", return_value=["array", "not", "object"]),
        pytest.raises(
            ValueError,
            match="Failed to load or parse env source file: JSON file content is not an object",
        ),
    ):
        parse_env_source("config.json")


def test_parse_env_source_type_conversion_error() -> None:
    """Test parse_env_source with values that can't be converted to strings."""

    class UnstringableObject:
        def __str__(self) -> str:
            raise TypeError("Cannot convert to string")

    with (
        patch("json.loads", return_value={"KEY1": UnstringableObject()}),
        pytest.raises(ValueError, match="Could not convert parsed env variables"),
    ):
        parse_env_source('{"KEY1": {}}')


def test_parse_env_source_json_decode_error() -> None:
    """Test parse_env_source error handling during JSON parsing with file load error."""
    with (
        patch("os.path.exists", return_value=True),
        patch("builtins.open", mock_open()),
        patch("json.load", side_effect=json.JSONDecodeError("Invalid JSON", "", 0)),
        pytest.raises(ValueError, match="Failed to load or parse env source file"),
    ):
        parse_env_source("config.json")
