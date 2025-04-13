import logging
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from pythonjsonlogger.json import JsonFormatter

from openapi_to_mcp.common.logger import configure_logger


@pytest.fixture
def mock_logger() -> Generator[MagicMock, None, None]:
    """
    Fixture to mock the logger for the 'openapi_to_mcp' package.

    Returns:
        MagicMock: Mocked logger instance.
    """
    with patch("logging.getLogger") as mock_get_logger:
        mock_logger_instance = MagicMock()
        mock_get_logger.return_value = mock_logger_instance
        yield mock_logger_instance


def test_configure_logger_default(mock_logger: MagicMock) -> None:
    """Test logger configuration with default settings (INFO level, text format)."""
    mock_logger.handlers = []

    configure_logger()

    mock_logger.setLevel.assert_called_once_with(logging.INFO)

    assert mock_logger.addHandler.call_count >= 1
    handler = mock_logger.addHandler.call_args[0][0]
    assert isinstance(handler, logging.StreamHandler)
    assert isinstance(handler.formatter, logging.Formatter)


def test_configure_logger_custom_level(mock_logger: MagicMock) -> None:
    """Test logger configuration with a custom logging level."""
    mock_logger.handlers = []

    configure_logger(level=logging.DEBUG)

    mock_logger.setLevel.assert_called_once_with(logging.DEBUG)

    assert mock_logger.addHandler.call_count >= 1
    handler = mock_logger.addHandler.call_args[0][0]
    assert isinstance(handler, logging.StreamHandler)

    assert isinstance(handler.formatter, logging.Formatter)


def test_configure_logger_json_format(mock_logger: MagicMock) -> None:
    """Test logger configuration with JSON format."""
    mock_logger.handlers = []

    configure_logger(log_format="json")

    mock_logger.setLevel.assert_called_once_with(logging.INFO)

    assert mock_logger.addHandler.call_count >= 1
    handler = mock_logger.addHandler.call_args[0][0]
    assert isinstance(handler, logging.StreamHandler)
    assert isinstance(handler.formatter, JsonFormatter)


def test_configure_logger_with_existing_handler(mock_logger: MagicMock) -> None:
    """Test that configure_logger doesn't add a duplicate handler."""
    mock_handler = MagicMock(spec=logging.StreamHandler)
    mock_logger.handlers = [mock_handler]

    configure_logger()

    assert mock_handler in mock_logger.handlers
