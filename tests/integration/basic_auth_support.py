"""Build generated Basic-auth projects and exercise their HTTP executor."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from openapi_to_mcp.cli import cli

BASIC_SCHEME = "__basic..auth--"
USERNAME_ENV = "AUTH_BASIC_AUTH_USERNAME"
PASSWORD_ENV = "AUTH_BASIC_AUTH_PASSWORD"  # noqa: S105 - environment variable name


@pytest.fixture(scope="module")
def basic_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Provide a compiled project shared by each module's request scenarios."""
    return build_basic_project(tmp_path_factory.mktemp("basic-auth") / "generated")


def basic_spec(scheme_name: str = BASIC_SCHEME) -> dict[str, Any]:
    """Return a spec with inherited, combined, alternative and public auth."""
    requirements = {
        "inherited": None,
        "both": [{scheme_name: [], "ExtraKey": []}],
        "fallback": [{"ExtraKey": [], scheme_name: []}, {"Bearer": []}],
        "basicFallback": [{"Bearer": []}, {scheme_name: []}],
        "optional": [{scheme_name: []}, {}],
        "public": [],
    }
    paths = {}
    for name, security in requirements.items():
        operation = {
            "operationId": name,
            "responses": {"200": {"description": "OK"}},
        }
        if security is not None:
            operation["security"] = security
        paths[f"/{name}"] = {"get": operation}
    return {
        "openapi": "3.0.3",
        "info": {"title": "Basic Auth", "version": "1.0"},
        "servers": [{"url": "https://api.example.com"}],
        "security": [{scheme_name: []}],
        "paths": paths,
        "components": {
            "securitySchemes": {
                scheme_name: {"type": "http", "scheme": "bAsIc"},
                "ExtraKey": {"type": "apiKey", "in": "header", "name": "X-Key"},
                "Bearer": {"type": "http", "scheme": "bearer"},
            }
        },
    }


def generate_basic_project(output: Path, scheme_name: str = BASIC_SCHEME) -> Path:
    """Generate a project without embedding any runtime credential values."""
    spec_path = output.parent / "basic.json"
    spec_path.write_text(json.dumps(basic_spec(scheme_name)), encoding="utf-8")
    result = CliRunner().invoke(
        cli,
        ["generate", "-o", str(spec_path), "--output-dir", str(output)],
    )
    assert result.exit_code == 0, result.output
    return output


def build_basic_project(output: Path, scheme_name: str = BASIC_SCHEME) -> Path:
    """Install and compile the generated server for request-level tests."""
    generate_basic_project(output, scheme_name)
    npm = shutil.which("npm")
    assert npm is not None, "npm is required for generated auth integration tests"
    for args in (
        ["install", "--ignore-scripts", "--no-audit", "--no-fund"],
        ["run", "build"],
    ):
        result = subprocess.run(  # noqa: S603
            [npm, *args],
            cwd=output,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    return output


def run_auth_case(output: Path, case: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Execute a tool against a loopback upstream and return capture plus logs."""
    node = shutil.which("node")
    assert node is not None
    script = Path(__file__).parents[1] / "resources/basic_auth_request.mjs"
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("AUTH_", "MCP_", "TARGET_API_"))
    }
    result = subprocess.run(  # noqa: S603
        [node, str(script), str(output)],
        input=json.dumps(case),
        cwd=output,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout), result.stderr
