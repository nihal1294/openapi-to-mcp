"""Conflicting auth headers must not silently satisfy an AND requirement."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.integration.basic_auth_support import (
    basic_project as basic_project,  # noqa: PLC0414 - pytest fixture
)
from tests.integration.basic_auth_support import run_auth_case

if TYPE_CHECKING:
    from pathlib import Path


def _case(scheme: dict, credential: str, *, reverse: bool = False) -> dict:
    names = ["Basic", "Other"]
    if reverse:
        names.reverse()
    return {
        "env": {
            "AUTH_BASIC_USERNAME": "wire-user",
            "AUTH_BASIC_PASSWORD": "wire-password",
            "AUTH_OTHER_USERNAME": "other-user",
            "AUTH_OTHER_PASSWORD": "other-password",
            "AUTH_OTHER_TOKEN": credential,
            "AUTH_OTHER_API_KEY": credential,
        },
        "metadata": {
            "security": [{name: [] for name in names}],
            "securitySchemes": {
                "Basic": {"type": "http", "scheme": "basic"},
                "Other": scheme,
            },
        },
    }


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize(
    "scheme",
    [
        {"type": "http", "scheme": "basic"},
        {"type": "http", "scheme": "bearer"},
        {"type": "oauth2"},
        {"type": "openIdConnect"},
        {"type": "apiKey", "in": "header", "name": "aUtHoRiZaTiOn"},
    ],
)
def test_conflicting_auth_headers_fail_before_http(
    basic_project: Path, scheme: dict, *, reverse: bool
) -> None:
    capture, logs = run_auth_case(
        basic_project, _case(scheme, "other-secret", reverse=reverse)
    )
    assert capture["requests"] == []
    result = capture["result"]
    assert result["_meta"]["error"] == {
        "code": "invalid_credentials",
        "source": "auth",
        "retryable": False,
    }
    assert "conflicting values for auth header" in result["content"][0]["text"]
    assert "other-secret" not in logs
    assert "wire-password" not in logs


def test_conflicting_requirement_allows_valid_alternative(basic_project: Path) -> None:
    case = _case({"type": "http", "scheme": "bearer"}, "fallback-token")
    case["metadata"]["security"].append({"Other": []})
    capture, _ = run_auth_case(basic_project, case)
    assert not capture["result"].get("isError", False)
    assert len(capture["requests"]) == 1
    assert capture["requests"][0]["headers"]["authorization"] == "Bearer fallback-token"


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("other_basic", [False, True])
def test_identical_auth_header_values_can_satisfy_both_schemes(
    basic_project: Path, *, reverse: bool, other_basic: bool
) -> None:
    scheme = (
        {"type": "http", "scheme": "basic"}
        if other_basic
        else {
            "type": "apiKey",
            "in": "header",
            "name": "aUtHoRiZaTiOn",
        }
    )
    case = _case(scheme, "Basic d2lyZS11c2VyOndpcmUtcGFzc3dvcmQ=", reverse=reverse)
    case["env"].update(
        {
            "AUTH_OTHER_USERNAME": "wire-user",
            "AUTH_OTHER_PASSWORD": "wire-password",
            "TARGET_API_AUTH_HEADER": "Authorization: Bearer raw-fallback",
        }
    )
    capture, _ = run_auth_case(basic_project, case)
    assert not capture["result"].get("isError", False)
    assert len(capture["requests"]) == 1
    assert capture["requests"][0]["headers"]["authorization"].startswith("Basic ")
