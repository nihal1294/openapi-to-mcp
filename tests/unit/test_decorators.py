import logging
from unittest.mock import patch

from openapi_to_mcp.common.decorators import handle_exceptions
from openapi_to_mcp.common.exceptions import OpenApiMcpError


class ComplexReturnValueError(Exception):
    """Custom exception for complex return value test."""


def test_handle_exceptions_no_exception() -> None:
    """Test that handle_exceptions passes through return value when no exception occurs."""

    @handle_exceptions(error_message="Test error")
    def test_func():
        return "success"

    result = test_func()
    assert result == "success"


def test_handle_exceptions_with_custom_openapi_mcp_error() -> None:
    """Test that handle_exceptions catches OpenApiMcpError."""

    @handle_exceptions(
        error_message="Custom error message", return_value="error_result"
    )
    def test_func():
        raise OpenApiMcpError("Test OpenApiMcpError")

    with patch("openapi_to_mcp.common.decorators.logger") as mock_logger:
        result = test_func()

        mock_logger.log.assert_called_once_with(
            logging.ERROR, "%s: %s", "Custom error message", "Test OpenApiMcpError"
        )

        assert result == "error_result"


def test_handle_exceptions_with_standard_exception() -> None:
    """Test that handle_exceptions catches standard exceptions."""

    @handle_exceptions(error_message="Standard error caught", return_value=False)
    def test_func():
        raise ValueError("Standard exception")

    with patch("openapi_to_mcp.common.decorators.logger") as mock_logger:
        result = test_func()

        mock_logger.log.assert_called_once()
        call_args = mock_logger.log.call_args[0]
        assert call_args[0] == logging.ERROR
        assert call_args[1] == "%s: %s"
        assert call_args[2] == "Standard error caught"
        assert call_args[3] == "Standard exception"
        assert mock_logger.log.call_args[1] == {"exc_info": True}

        assert result is False


def test_handle_exceptions_with_custom_log_level() -> None:
    """Test that handle_exceptions uses the specified log level."""

    @handle_exceptions(
        error_message="Warning level message",
        return_value="warning",
        log_level=logging.WARNING,
    )
    def test_func():
        raise OpenApiMcpError("Warning test")

    with patch("openapi_to_mcp.common.decorators.logger") as mock_logger:
        result = test_func()

        mock_logger.log.assert_called_once()
        assert mock_logger.log.call_args[0][0] == logging.WARNING

        assert result == "warning"


def test_handle_exceptions_with_complex_return_value() -> None:
    """Test handle_exceptions with a complex return value like a dict."""

    return_dict = {"status": "error", "code": 500}

    @handle_exceptions(error_message="Error occurred", return_value=return_dict)
    def test_func():
        raise ComplexReturnValueError("Complex return value test")

    result = test_func()
    assert result is return_dict
    assert result["status"] == "error"
    assert result["code"] == 500


def test_handle_exceptions_with_function_arguments() -> None:
    """Test that handle_exceptions preserves function arguments."""

    @handle_exceptions(error_message="Args error")
    def test_func(a, b=10):
        return a + b

    assert test_func(5) == 15
    assert test_func(5, 20) == 25
    assert test_func(a=15, b=30) == 45
