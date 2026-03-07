from __future__ import annotations

import functools
import logging
from typing import TYPE_CHECKING, ParamSpec, TypeVar

from openapi_to_mcp.common.exceptions import OpenApiMcpError

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")
P = ParamSpec("P")


def handle_exceptions(  # noqa: UP047
    error_message: str = "An error occurred",
    return_value: R = None,  # type: ignore[assignment]
    log_level: int = logging.ERROR,
) -> Callable[[Callable[P, T]], Callable[P, T | R]]:
    """
    Decorator to handle exceptions in a consistent way.

    Args:
        error_message: Message to log when an exception occurs
        return_value: Value to return when an exception occurs
        log_level: Logging level to use when an exception occurs

    Returns:
        Decorated function that handles exceptions
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T | R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T | R:
            try:
                return func(*args, **kwargs)
            except OpenApiMcpError as e:
                logger.log(log_level, "%s: %s", error_message, str(e))
                return return_value
            except Exception as e:  # noqa: BLE001
                logger.log(log_level, "%s: %s", error_message, str(e), exc_info=True)
                return return_value

        return wrapper

    return decorator
