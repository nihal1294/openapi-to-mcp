"""Swagger compatibility checks respect the effective generation policy."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
import yaml

from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner


@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize(
    "policy",
    [
        {"auth": {"operations": {"GET /status": {"security": []}}}},
        {"auth": {"names": {"getStatus": {"security": []}}}},
        {
            "tools": {"rename": {"names": {"getStatus": "publicStatus"}}},
            "auth": {"names": {"publicStatus": {"security": []}}},
        },
    ],
)
def test_swagger_auth_policy_can_make_operation_public(
    runner: CliRunner, tmp_path: Path, policy: dict, *, strict: bool
) -> None:
    result = _generate(runner, tmp_path, policy, strict=strict)

    assert result.exit_code == 0, result.output
    report = json.loads((tmp_path / "output/generation_report.json").read_text())
    assert report["mapped_tools"] == 1
    assert report["skipped_operations"] == []
    runtime = (tmp_path / "output/src/runtime/generated.ts").read_text()
    assert '"security": []' in runtime


@pytest.mark.parametrize(
    ("scheme", "credential"),
    [
        ({"type": "apiKey", "in": "header", "name": "X-Key"}, "API_KEY"),
        ({"type": "apiKey", "in": "query", "name": "key"}, "API_KEY"),
        ({"type": "apiKey", "in": "cookie", "name": "key"}, "API_KEY"),
        ({"type": "http", "scheme": "bearer"}, "TOKEN"),
        ({"type": "oauth2"}, "TOKEN"),
        ({"type": "openIdConnect"}, "TOKEN"),
    ],
)
def test_swagger_auth_policy_can_supply_runtime_security(
    runner: CliRunner, tmp_path: Path, scheme: dict, credential: str
) -> None:
    policy = {
        "auth": {
            "operations": {
                "GET /status": {
                    "security": [{"Replacement": []}],
                    "security_schemes": {"Replacement": scheme},
                }
            }
        }
    }

    result = _generate(runner, tmp_path, policy)

    assert result.exit_code == 0, result.output
    assert (
        f"AUTH_REPLACEMENT_{credential}"
        in (tmp_path / "output/.env.example").read_text()
    )


@pytest.mark.parametrize(
    "scheme",
    [
        {},
        {"type": "basic"},
        {"type": "http", "scheme": "basic"},
        {"type": "http"},
        {"type": "apiKey", "in": "body", "name": "key"},
        {"type": "apiKey", "in": "path", "name": "key"},
        {"type": "apiKey", "name": "key"},
        {"type": "apiKey", "in": None, "name": "key"},
        {"type": "apiKey", "in": 42, "name": "key"},
        {"type": "apiKey", "in": "header"},
        {"type": "apiKey", "in": "header", "name": ""},
        {"type": "apiKey", "in": "query", "name": None},
        {"type": "apiKey", "in": "cookie", "name": 42},
        {"type": "apiKey", "in": "cookie", "name": " "},
    ],
)
@pytest.mark.parametrize("strict", [True, False])
def test_swagger_auth_policy_rejects_unsupported_runtime_security(
    runner: CliRunner, tmp_path: Path, scheme: dict, *, strict: bool
) -> None:
    policy = {
        "auth": {
            "operations": {
                "GET /status": {
                    "security": [{"Replacement": []}],
                    "security_schemes": {"Replacement": scheme},
                }
            }
        }
    }
    spec = _spec()
    spec["paths"]["/public"] = {
        "get": {"security": [], "responses": {"200": {"description": "OK"}}}
    }

    result = _generate(runner, tmp_path, policy, strict=strict, spec=spec)

    if strict:
        assert result.exit_code != 0
        assert "unsupported Swagger 2" in result.output
    else:
        assert result.exit_code == 0, result.output
        report = json.loads((tmp_path / "output/generation_report.json").read_text())
        assert report["mapped_tools"] == 1
        assert [entry["path"] for entry in report["skipped_operations"]] == ["/status"]


@pytest.mark.parametrize(
    "policy",
    [
        {"auth": {"operations": {"GET /other": {"security": []}}}},
        {"auth": {"operations": {"GET /status": {"security": [{"Missing": []}]}}}},
    ],
)
def test_swagger_unresolved_auth_still_fails(
    runner: CliRunner, tmp_path: Path, policy: dict
) -> None:
    result = _generate(runner, tmp_path, policy)

    assert result.exit_code != 0
    assert "unsupported Swagger 2" in result.output


def test_swagger_auth_policy_does_not_hide_unsupported_parameters(
    runner: CliRunner, tmp_path: Path
) -> None:
    spec = _spec()
    spec["paths"]["/status"]["get"]["parameters"] = [
        {"name": "limit", "in": "query", "type": "integer"}
    ]
    result = _generate(
        runner,
        tmp_path,
        {"auth": {"operations": {"GET /status": {"security": []}}}},
        spec=spec,
    )

    assert result.exit_code != 0
    assert "unsupported Swagger 2" in result.output


def _generate(runner, tmp_path, policy, *, strict=True, spec=None):
    spec_path = tmp_path / "swagger.json"
    policy_path = tmp_path / "mcpgen.yaml"
    spec_path.write_text(json.dumps(spec or _spec()))
    policy_path.write_text(yaml.safe_dump(policy))
    return runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            str(spec_path),
            "--config",
            str(policy_path),
            "--output-dir",
            str(tmp_path / "output"),
            "--strict" if strict else "--no-strict",
        ],
    )


def _spec() -> dict:
    return {
        "swagger": "2.0",
        "info": {"title": "Policy compatibility", "version": "1.0"},
        "host": "api.example.com",
        "securityDefinitions": {
            "Legacy": {"type": "apiKey", "in": "header", "name": "X-Key"}
        },
        "security": [{"Legacy": []}],
        "paths": {
            "/status": {
                "get": {
                    "operationId": "getStatus",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
