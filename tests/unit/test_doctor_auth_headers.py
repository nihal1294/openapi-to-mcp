from __future__ import annotations

from typing import Any

import pytest

from openapi_to_mcp.doctor import DoctorAnalyzer

_SCHEMES: dict[str, dict[str, Any]] = {
    "Basic": {"type": "http", "scheme": "basic"},
    "BasicTwo": {"type": "http", "scheme": "Basic"},
    "Bearer": {"type": "http", "scheme": "bearer"},
    "ExtraKey": {"type": "apiKey", "in": "header", "name": "X-Key"},
    "AuthorizationKey": {
        "type": "apiKey",
        "in": "header",
        "name": "authorization",
    },
}


def _spec(
    security: object,
    *,
    operation_security: bool = False,
    schemes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    operation: dict[str, Any] = {
        "operationId": "getThing",
        "responses": {"200": {"description": "OK"}},
    }
    spec: dict[str, Any] = {
        "openapi": "3.0.3",
        "info": {"title": "Auth headers", "version": "1.0.0"},
        "servers": [{"url": "https://example.com"}],
        "components": {"securitySchemes": schemes or _SCHEMES},
        "paths": {"/thing": {"get": operation}},
    }
    if operation_security:
        operation["security"] = security
    else:
        spec["security"] = security
    return spec


def _issues(spec: dict[str, Any]) -> list[Any]:
    return DoctorAnalyzer(spec).analyze("inline").issues


@pytest.mark.parametrize(
    ("requirement", "scheme_names"),
    [
        ({"Basic": [], "Bearer": []}, ("Basic", "Bearer")),
        ({"Basic": [], "AuthorizationKey": []}, ("Basic", "AuthorizationKey")),
        ({"Basic": [], "BasicTwo": []}, ("Basic", "BasicTwo")),
    ],
)
@pytest.mark.parametrize(
    ("operation_security", "location"),
    [(False, "security"), (True, "paths./thing.get.security")],
)
def test_doctor_warns_for_duplicate_auth_headers(
    requirement: dict[str, list[str]],
    scheme_names: tuple[str, str],
    *,
    operation_security: bool,
    location: str,
) -> None:
    issues = _issues(_spec([requirement], operation_security=operation_security))

    conflicts = [issue for issue in issues if issue.code == "conflicting_auth_headers"]
    assert len(conflicts) == 1
    assert conflicts[0].severity == "warning"
    assert conflicts[0].location == location
    assert all(name in conflicts[0].message for name in scheme_names)
    assert "alternatives" in conflicts[0].hint


@pytest.mark.parametrize(
    "security",
    [
        [{"Basic": [], "ExtraKey": []}],
        [{"Basic": []}, {"Bearer": []}],
    ],
)
def test_doctor_allows_distinct_headers_and_security_alternatives(
    security: list[dict[str, list[str]]],
) -> None:
    issues = _issues(_spec(security))

    assert not any(issue.code == "conflicting_auth_headers" for issue in issues)


def test_doctor_ignores_malformed_security_metadata_for_extra_check() -> None:
    schemes: dict[str, Any] = {
        "Basic": _SCHEMES["Basic"],
        "Broken": None,
    }
    issues = _issues(_spec([{"Basic": [], "Broken": None}], schemes=schemes))

    assert any(issue.code == "undefined_security_scheme" for issue in issues)
    assert not any(issue.code == "conflicting_auth_headers" for issue in issues)
