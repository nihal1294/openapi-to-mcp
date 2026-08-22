"""Behavior expectations used by generated-server E2E suites."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolExpectation:
    """Expected behavior for one generated MCP tool."""

    name: str
    arguments: dict[str, Any]
    expected: dict[str, Any] | None = None
    expected_error: str | None = None
    expected_error_meta: dict[str, Any] | None = None


SUITES: dict[str, list[ToolExpectation]] = {
    "basic": [
        ToolExpectation(
            name="testConversionTool",
            arguments={"status": "available"},
            expected={"status": "available"},
        )
    ],
    "auth": [
        ToolExpectation(
            name="getHeaderAuth",
            arguments={},
            expected={"auth": "header", "credential": "header-secret"},
        ),
        ToolExpectation(
            name="getQueryAuth",
            arguments={},
            expected={"auth": "query", "credential": "query-secret"},
        ),
        ToolExpectation(
            name="getCookieAuth",
            arguments={},
            expected={"auth": "cookie", "credential": "cookie-secret"},
        ),
        ToolExpectation(
            name="getBearerAuth",
            arguments={},
            expected={"auth": "bearer", "credential": "bearer-secret"},
        ),
    ],
    "auth-missing-bearer": [
        ToolExpectation(
            name="getBearerAuth",
            arguments={},
            expected_error="AUTH_BEARERAUTH_TOKEN",
            expected_error_meta={
                "code": "missing_credentials",
                "source": "auth",
                "retryable": False,
            },
        )
    ],
    "validation-failure": [
        ToolExpectation(
            name="testConversionTool",
            arguments={"status": 123},
            expected_error="Input validation failed",
            expected_error_meta={
                "code": "input_validation_failed",
                "source": "validation",
                "retryable": False,
            },
        )
    ],
    "validation-disabled": [
        ToolExpectation(
            name="testConversionTool",
            arguments={"status": 123},
            expected={"status": "123"},
        )
    ],
    "grouped": [
        ToolExpectation(
            name="test_testConversionTool",
            arguments={"status": "available"},
            expected={"status": "available"},
        )
    ],
    "upstream-server-error": [
        ToolExpectation(
            name="testConversionTool",
            arguments={"status": "server_error"},
            expected_error="API server error (503)",
            expected_error_meta={
                "code": "api_server_error",
                "source": "upstream",
                "retryable": True,
                "httpStatus": 503,
            },
        )
    ],
}
