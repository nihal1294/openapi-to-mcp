"""Logging configuration for the openapi-to-mcp package."""

from __future__ import annotations

import logging
import sys
from typing import Literal

import structlog

LogFormat = Literal["text", "json"]


def _build_shared_processors() -> list[structlog.types.Processor]:
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.stdlib.ExtraAdder(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
    ]


def _build_formatter(log_format: LogFormat) -> structlog.stdlib.ProcessorFormatter:
    renderer: structlog.types.Processor
    if log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    return structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=_build_renderer_processors(log_format),
        processor=renderer,
    )


def _build_renderer_processors(
    log_format: LogFormat,
) -> list[structlog.types.Processor]:
    processors = _build_shared_processors()
    if log_format == "json":
        processors.append(structlog.processors.format_exc_info)
    return processors


def _configure_structlog(log_format: LogFormat) -> None:
    structlog.configure(
        processors=[
            *_build_renderer_processors(log_format),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def configure_logger(
    logger_name: str = "openapi_to_mcp",
    level: int = logging.INFO,
    log_format: LogFormat = "text",
) -> None:
    """Configure package logging with structlog-backed rendering."""
    if log_format not in {"text", "json"}:
        raise ValueError("Invalid log_format. Supported formats are 'text' and 'json'.")

    _configure_structlog(log_format)

    package_logger = logging.getLogger(logger_name)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_build_formatter(log_format))

    package_logger.handlers.clear()
    package_logger.addHandler(handler)
    package_logger.setLevel(level)
    package_logger.propagate = False
