"""Exercise generated Basic authentication over real loopback HTTP requests."""

from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING

import pytest

from tests.integration.basic_auth_support import (
    PASSWORD_ENV,
    USERNAME_ENV,
    run_auth_case,
)
from tests.integration.basic_auth_support import (
    basic_project as basic_project,  # noqa: PLC0414 - pytest fixture
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("wire-user", "wire-password"),
        ("tökén", "päss:word £"),
        ("token-user", ""),
        (" user ", " pass "),
    ],
)
def test_basic_header_and_audit_redaction(
    basic_project: Path, username: str, password: str
) -> None:
    capture, logs = run_auth_case(
        basic_project,
        {
            "env": {
                USERNAME_ENV: username,
                PASSWORD_ENV: password,
                "TARGET_API_AUTH_HEADER": "Authorization: Bearer fallback-token",
            }
        },
    )
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
    assert not capture["result"].get("isError", False)
    assert len(capture["requests"]) == 1
    assert capture["requests"][0]["headers"]["authorization"] == f"Basic {encoded}"
    assert capture["requests"][0]["path"] == "/inherited"
    audit = [json.loads(line) for line in logs.splitlines() if line.startswith("{")]
    request = next(event for event in audit if event["event"] == "tool_audit_request")
    assert request["headers"]["Authorization"] == "[REDACTED]"
    observable = logs + json.dumps(capture["result"])
    assert username not in observable
    assert not password or password not in observable
    assert encoded not in observable


@pytest.mark.parametrize(
    ("env", "missing"),
    [
        ({}, [USERNAME_ENV, PASSWORD_ENV]),
        ({USERNAME_ENV: ""}, [USERNAME_ENV, PASSWORD_ENV]),
        ({PASSWORD_ENV: ""}, [USERNAME_ENV]),
        ({USERNAME_ENV: "secret-user"}, [PASSWORD_ENV]),
        ({PASSWORD_ENV: "secret-password"}, [USERNAME_ENV]),
    ],
)
def test_missing_basic_credentials_stop_before_http(
    basic_project: Path, env: dict, missing: list[str]
) -> None:
    capture, logs = run_auth_case(basic_project, {"env": env})
    result = capture["result"]
    assert capture["requests"] == []
    assert result["isError"] is True
    assert result["_meta"]["error"] == {
        "code": "missing_credentials",
        "source": "auth",
        "retryable": False,
    }
    for name in missing:
        assert name in result["content"][0]["text"]
    for value in env.values():
        assert not value or value not in logs + json.dumps(result)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (USERNAME_ENV, "bad:user"),
        (USERNAME_ENV, "bad\nuser"),
        (PASSWORD_ENV, "bad\rpassword"),
        (PASSWORD_ENV, "bad\x7fpassword"),
        (PASSWORD_ENV, "bad\tpassword"),
    ],
)
def test_invalid_basic_credentials_stop_before_http(
    basic_project: Path, field: str, value: str
) -> None:
    env = {USERNAME_ENV: "secret-user", PASSWORD_ENV: "secret-password", field: value}
    capture, logs = run_auth_case(basic_project, {"env": env})
    result = capture["result"]
    assert capture["requests"] == []
    assert result["_meta"]["error"] == {
        "code": "invalid_credentials",
        "source": "auth",
        "retryable": False,
    }
    assert field in result["content"][0]["text"]
    for secret in env.values():
        assert secret not in logs
        assert secret not in result["content"][0]["text"]


@pytest.mark.parametrize("username", [None, "bad:user"])
def test_failed_basic_alternative_does_not_leak_headers(
    basic_project: Path, username: str | None
) -> None:
    env = {
        "AUTH_EXTRAKEY_API_KEY": "failed-branch-key",
        "AUTH_BEARER_TOKEN": "fallback-token",
    }
    if username is not None:
        env[USERNAME_ENV] = username
        env[PASSWORD_ENV] = "secret-password"
    capture, _ = run_auth_case(basic_project, {"tool": "fallback", "env": env})
    assert not capture["result"].get("isError", False)
    headers = capture["requests"][0]["headers"]
    assert headers["authorization"] == "Bearer fallback-token"
    assert "x-key" not in headers


@pytest.mark.parametrize("with_key", [True, False])
def test_basic_and_api_key_require_both(basic_project: Path, *, with_key: bool) -> None:
    env = {USERNAME_ENV: "wire-user", PASSWORD_ENV: "wire-password"}
    if with_key:
        env["AUTH_EXTRAKEY_API_KEY"] = "wire-key"
    capture, _ = run_auth_case(basic_project, {"tool": "both", "env": env})
    if with_key:
        assert not capture["result"].get("isError", False)
        assert capture["requests"][0]["headers"]["x-key"] == "wire-key"
        assert capture["requests"][0]["headers"]["authorization"].startswith("Basic ")
    else:
        assert capture["requests"] == []
        assert capture["result"]["_meta"]["error"]["code"] == "missing_credentials"


@pytest.mark.parametrize("tool", ["optional", "public"])
def test_public_requirement_needs_no_basic_credentials(
    basic_project: Path, tool: str
) -> None:
    capture, _ = run_auth_case(basic_project, {"tool": tool, "env": {}})
    assert not capture["result"].get("isError", False)
    assert "authorization" not in capture["requests"][0]["headers"]


def test_rejected_basic_credentials_remain_upstream_error(basic_project: Path) -> None:
    capture, _ = run_auth_case(
        basic_project,
        {
            "status": 401,
            "env": {
                USERNAME_ENV: "wire-user",
                PASSWORD_ENV: "wrong-password",
            },
        },
    )
    assert len(capture["requests"]) == 1
    error = capture["result"]["_meta"]["error"]
    assert error["code"] == "api_authorization_failed"
    assert error["source"] == "upstream"
    assert error["retryable"] is False


def test_basic_satisfies_alternative_after_missing_bearer(basic_project: Path) -> None:
    capture, _ = run_auth_case(
        basic_project,
        {
            "tool": "basicFallback",
            "env": {
                USERNAME_ENV: "wire-user",
                PASSWORD_ENV: "wire-password",
            },
        },
    )
    assert not capture["result"].get("isError", False)
    assert len(capture["requests"]) == 1
    assert capture["requests"][0]["headers"]["authorization"].startswith("Basic ")
