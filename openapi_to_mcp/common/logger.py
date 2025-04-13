import logging
import sys

from pythonjsonlogger.json import JsonFormatter


def configure_logger(
    logger_name: str = "openapi_to_mcp",
    level: int = logging.INFO,
    log_format: str = "text",
) -> None:
    """
    Configures the root logger for the 'openapi_to_mcp' package.

    Sets up a single StreamHandler with a JsonFormatter. Should be called
    once at the start of the application.

    Args:
        logger_name (str): The name of the logger to configure.
                           Defaults to 'openapi_to_mcp'.
        level (int): The logging level to set for the root logger.
                     Defaults to logging.INFO.
        log_format (str): The format to use for logging. Currently not used
                      but included for future extensibility.
    """
    if log_format not in ["text", "json"]:
        raise ValueError("Invalid log_format. Supported formats are 'text' and 'json'.")

    pkg_logger = logging.getLogger(logger_name)

    # Avoid adding duplicate handlers
    if not any(isinstance(h, logging.StreamHandler) for h in pkg_logger.handlers):
        handler = logging.StreamHandler(sys.stderr)
        if log_format == "json":
            formatter = JsonFormatter("%(asctime)s %(name)s %(levelname)s %(message)s")
        else:
            formatter = logging.Formatter(
                "%(asctime)s %(name)s %(levelname)s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        handler.setFormatter(formatter)
        pkg_logger.addHandler(handler)

    pkg_logger.setLevel(level)
    pkg_logger.propagate = True
