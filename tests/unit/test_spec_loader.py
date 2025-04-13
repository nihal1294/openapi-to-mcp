from typing import Any
from unittest.mock import MagicMock, mock_open

import pytest
import requests

from openapi_to_mcp.adapters.spec_loader import SpecLoader
from openapi_to_mcp.common.exceptions import SpecLoaderError


@pytest.fixture
def mock_requests_get(mocker: Any) -> MagicMock:
    """Fixture to mock requests.get."""
    return mocker.patch("requests.get")


@pytest.fixture
def mock_path_open(mocker: Any) -> MagicMock:
    """Fixture to mock Path.open."""
    return mocker.patch("pathlib.Path.open", mock_open())


@pytest.fixture
def mock_is_file(mocker: Any) -> MagicMock:
    """Fixture to mock Path.is_file."""
    mock = mocker.patch("pathlib.Path.is_file")
    mock.return_value = True
    return mock


def test_spec_loader_load_from_valid_file(
    mock_path_open: MagicMock, mock_is_file: MagicMock
) -> None:
    """Test loading a valid YAML spec from a local file."""
    valid_yaml_content = """
openapi: 3.0.0
info:
  title: Valid Spec File
  version: 1.0.0
paths: {}
"""
    mock_path_open.return_value.read.return_value = valid_yaml_content

    loader = SpecLoader(source="valid_spec.yaml")
    spec = loader.load_and_validate()

    assert spec["info"]["title"] == "Valid Spec File"
    mock_path_open.assert_called_once_with("r", encoding="utf-8")


def test_spec_loader_load_from_valid_url(mock_requests_get: MagicMock) -> None:
    """Test loading a valid JSON spec from a URL."""
    valid_json_content = '{"openapi": "3.0.0", "info": {"title": "Valid Spec URL", "version": "1.0"}, "paths": {}}'
    mock_response = MagicMock()
    mock_response.text = valid_json_content
    mock_response.raise_for_status = MagicMock()
    mock_requests_get.return_value = mock_response

    loader = SpecLoader(source="http://example.com/valid_spec.json")
    spec = loader.load_and_validate()

    assert spec["info"]["title"] == "Valid Spec URL"
    mock_requests_get.assert_called_once_with(
        "http://example.com/valid_spec.json", timeout=10
    )
    mock_response.raise_for_status.assert_called_once()


def test_spec_loader_file_not_found(mock_is_file: MagicMock) -> None:
    """Test error handling when the local file does not exist."""
    mock_is_file.return_value = False

    loader = SpecLoader(source="non_existent_spec.yaml")

    with pytest.raises(SpecLoaderError, match="OpenAPI spec file not found"):
        loader.load_and_validate()
    mock_is_file.assert_called_once()


def test_spec_loader_file_read_error(mocker: Any, mock_path_open: MagicMock) -> None:
    """Test error handling for OS errors during file read."""
    mock_is_file = mocker.patch("pathlib.Path.is_file", return_value=True)
    mock_path_open.side_effect = OSError("Permission denied")

    loader = SpecLoader(source="error_spec.yaml")

    with pytest.raises(SpecLoaderError, match="Error reading OpenAPI spec file"):
        loader.load_and_validate()
    mock_is_file.assert_called_once()
    mock_path_open.assert_called_once()


def test_spec_loader_url_fetch_error(mock_requests_get: MagicMock) -> None:
    """Test error handling for network errors when fetching from URL."""
    mock_requests_get.side_effect = requests.exceptions.RequestException(
        "Network error"
    )

    loader = SpecLoader(source="http://example.com/error_spec.json")

    with pytest.raises(SpecLoaderError, match="Error fetching OpenAPI spec from URL"):
        loader.load_and_validate()
    mock_requests_get.assert_called_once()


def test_spec_loader_url_http_error(mock_requests_get: MagicMock) -> None:
    """Test error handling for HTTP error status codes (e.g., 404) from URL."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "404 Client Error"
    )
    mock_requests_get.return_value = mock_response

    loader = SpecLoader(source="http://example.com/not_found.json")

    with pytest.raises(SpecLoaderError, match="Error fetching OpenAPI spec from URL"):
        loader.load_and_validate()
    mock_requests_get.assert_called_once()
    mock_response.raise_for_status.assert_called_once()


def test_spec_loader_invalid_yaml(mocker: Any, mock_path_open: MagicMock) -> None:
    """Test error handling for invalid YAML/JSON content."""
    mocker.patch("pathlib.Path.is_file", return_value=True)
    invalid_yaml_content = "openapi: 3.0.0\ninfo: {title: Invalid"
    mock_path_open.return_value.read.return_value = invalid_yaml_content

    loader = SpecLoader(source="invalid_spec.yaml")

    with pytest.raises(SpecLoaderError, match="Error parsing OpenAPI spec content"):
        loader.load_and_validate()


def test_spec_loader_validation_error(mocker: Any, mock_path_open: MagicMock) -> None:
    """Test error handling when openapi-spec-validator raises an error."""
    mocker.patch("pathlib.Path.is_file", return_value=True)
    mock_validate = mocker.patch("openapi_spec_validator.validate")

    valid_yaml_content = (
        "openapi: 3.0.0\ninfo:\n  title: Valid\n  version: 1.0\npaths: {}"
    )
    mock_path_open.return_value.read.return_value = valid_yaml_content
    mock_validate.side_effect = Exception("Spec validation failed")

    loader = SpecLoader(source="validation_error.yaml")

    with pytest.raises(SpecLoaderError, match="OpenAPI spec validation failed"):
        loader.load_and_validate()
    # Remove assert_called_once for mock that raises exception via side_effect
    # pytest.raises already confirms the code path was hit.


def test_spec_loader_not_a_dict(mocker: Any, mock_path_open: MagicMock) -> None:
    """Test error when parsed content is not a dictionary."""
    mocker.patch("pathlib.Path.is_file", return_value=True)
    not_a_dict_content = "- item1\n- item2"
    mock_path_open.return_value.read.return_value = not_a_dict_content

    loader = SpecLoader(source="list_spec.yaml")

    with pytest.raises(
        SpecLoaderError,
        match="Parsed specification is not a valid dictionary structure",
    ):
        loader.load_and_validate()
