from __future__ import annotations

import json
import logging
from uuid import uuid4

import pytest
from structlog.stdlib import ProcessorFormatter

from openapi_to_mcp.common.logger import configure_logger


def _unique_logger_name() -> str:
    return f"openapi_to_mcp.tests.{uuid4().hex}"


def _reset_logger(logger_name: str) -> logging.Logger:
    logger = logging.getLogger(logger_name)
    logger.handlers.clear()
    logger.propagate = True
    logger.setLevel(logging.NOTSET)
    return logger


def test_configure_logger_default() -> None:
    logger_name = _unique_logger_name()
    logger = _reset_logger(logger_name)

    configure_logger(logger_name=logger_name)

    assert logger.level == logging.INFO
    assert logger.propagate is False
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.StreamHandler)
    assert isinstance(logger.handlers[0].formatter, ProcessorFormatter)


def test_configure_logger_custom_level() -> None:
    logger_name = _unique_logger_name()
    logger = _reset_logger(logger_name)

    configure_logger(logger_name=logger_name, level=logging.DEBUG)

    assert logger.level == logging.DEBUG


def test_configure_logger_json_format_renders_json() -> None:
    logger_name = _unique_logger_name()
    logger = _reset_logger(logger_name)

    configure_logger(logger_name=logger_name, log_format="json")

    record = logging.LogRecord(
        name=logger_name,
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    formatted = logger.handlers[0].formatter.format(record)

    payload = json.loads(formatted)
    assert payload["event"] == "hello"
    assert payload["level"] == "info"


def test_configure_logger_replaces_existing_handlers() -> None:
    logger_name = _unique_logger_name()
    logger = _reset_logger(logger_name)
    logger.addHandler(logging.NullHandler())

    configure_logger(logger_name=logger_name)
    configure_logger(logger_name=logger_name)

    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.StreamHandler)


def test_configure_logger_rejects_invalid_format() -> None:
    with pytest.raises(ValueError, match="Invalid log_format"):
        configure_logger(log_format="xml")  # type: ignore[arg-type]
