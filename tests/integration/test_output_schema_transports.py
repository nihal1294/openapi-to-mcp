"""Check advertised output schemas against generated server wire results."""

from __future__ import annotations

import json
import os
import select
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

import pytest
import requests
from click.testing import CliRunner
from jsonschema import Draft202012Validator

from openapi_to_mcp.cli import cli
from tests.integration.http_health_support import running_server

if TYPE_CHECKING:
    from pathlib import Path


def _spec() -> dict:
    def response(field: str) -> dict:
        return {
            "description": "ok",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {field: {"type": "string"}},
                        "required": [field],
                    }
                }
            },
        }

    return {
        "openapi": "3.0.0",
        "info": {"title": "Outcomes", "version": "1"},
        "paths": {
            "/union": {
                "get": {
                    "operationId": "union",
                    "responses": {"200": response("a"), "201": response("b")},
                }
            },
            "/wildcard": {
                "get": {"operationId": "wildcard", "responses": {"2XX": response("a")}}
            },
            "/default": {
                "get": {
                    "operationId": "default",
                    "responses": {"default": response("a")},
                }
            },
            "/exclusive": {
                "get": {
                    "operationId": "exclusive",
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "oneOf": [
                                            {"type": "object", "maxProperties": 1},
                                            {"type": "object", "minProperties": 2},
                                        ]
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/scalar": {
                "get": {
                    "operationId": "scalar",
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "anyOf": [
                                            {"properties": {"a": {"type": "string"}}},
                                            {"properties": {"b": {"type": "string"}}},
                                        ]
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/mixed": {
                "get": {
                    "operationId": "mixed",
                    "responses": {
                        "200": response("a"),
                        "204": {"description": "empty"},
                    },
                }
            },
        },
    }


@pytest.fixture(scope="module", params=["stdio", "streamable-http"])
def project(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> tuple[Path, str]:
    root = tmp_path_factory.mktemp("output-transport")
    spec = root / "spec.json"
    spec.write_text(json.dumps(_spec()), encoding="utf-8")
    output = root / "generated"
    result = CliRunner().invoke(
        cli,
        [
            "generate",
            "-o",
            str(spec),
            "--output-dir",
            str(output),
            "--transport",
            request.param,
        ],
    )
    assert result.exit_code == 0, result.output
    npm = shutil.which("npm")
    assert npm is not None
    for args in (
        ["install", "--ignore-scripts", "--no-audit", "--no-fund"],
        ["run", "build"],
    ):
        run = subprocess.run(  # noqa: S603
            [npm, *args],
            cwd=output,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        assert run.returncode == 0, run.stdout + run.stderr
    return output, request.param


class Upstream(BaseHTTPRequestHandler):
    status = 200
    exclusive_body = b"{}"

    def do_GET(self) -> None:
        self.send_response(self.status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if self.status not in (204, 205) and self.path == "/exclusive":
            self.wfile.write(self.exclusive_body)
        elif self.status not in (204, 205) and self.path == "/scalar":
            self.wfile.write(b'"hello"')
        elif self.status not in (204, 205):
            self.wfile.write(
                b'{"a":"ok"}' if self.status == 200 else b'{"b":"created"}'
            )

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


def _exercise(rpc: object) -> None:
    call = rpc
    tools = {tool["name"]: tool for tool in call("tools/list", {})["tools"]}
    schema = tools["union"]["outputSchema"]
    for name in ("mixed", "wildcard", "default", "scalar", "exclusive"):
        assert "outputSchema" not in tools[name]
    validator = Draft202012Validator(schema)
    for status, expected in ((200, {"a": "ok"}), (201, {"b": "created"})):
        Upstream.status = status
        result = call("tools/call", {"name": "union", "arguments": {}})
        assert not result.get("isError", False)
        assert result["structuredContent"] == expected
        validator.validate(result["structuredContent"])
    Upstream.status = 200
    result = call("tools/call", {"name": "mixed", "arguments": {}})
    assert not result.get("isError", False)
    assert result["content"][0]["type"] == "text"
    Upstream.status = 204
    result = call("tools/call", {"name": "mixed", "arguments": {}})
    assert not result.get("isError", False)
    assert result["content"][0]["type"] == "text"
    for name in ("wildcard", "default"):
        for status in (204, 205):
            Upstream.status = status
            result = call("tools/call", {"name": name, "arguments": {}})
            assert not result.get("isError", False)
            assert result["content"][0]["type"] == "text"
            assert "structuredContent" not in result
    Upstream.status = 200
    result = call("tools/call", {"name": "scalar", "arguments": {}})
    assert not result.get("isError", False)
    assert result["content"][0]["text"] == "hello"
    assert "structuredContent" not in result
    exclusive_schema = _spec()["paths"]["/exclusive"]["get"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]
    for payload in ({"a": 1}, {"a": 1, "b": 2}):
        Draft202012Validator(exclusive_schema).validate(payload)
        Upstream.exclusive_body = json.dumps(payload).encode()
        result = call("tools/call", {"name": "exclusive", "arguments": {}})
        assert not result.get("isError", False)
        assert json.loads(result["content"][0]["text"]) == payload


def test_output_schema_on_transport(project: tuple[Path, str]) -> None:
    output, transport = project
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{upstream.server_port}"
    init = {
        "protocolVersion": "2025-11-25",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"},
    }
    try:
        if transport == "stdio":
            env = {
                k: v
                for k, v in os.environ.items()
                if not k.startswith(("MCP_", "AUTH_", "TARGET_API_"))
            }
            env.update(TARGET_API_BASE_URL=url, TERM="dumb", NO_COLOR="1")
            process = subprocess.Popen(  # noqa: S603
                [shutil.which("node"), "build/index.js"],
                cwd=output,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            assert process.stdin
            assert process.stdout
            index = 0

            def rpc(method: str, params: dict) -> dict:
                nonlocal index
                index += 1
                process.stdin.write(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": index,
                            "method": method,
                            "params": params,
                        }
                    )
                    + "\n"
                )
                process.stdin.flush()
                assert select.select([process.stdout], [], [], 10)[0]
                return json.loads(process.stdout.readline())["result"]

            try:
                rpc("initialize", init)
                process.stdin.write(
                    json.dumps(
                        {"jsonrpc": "2.0", "method": "notifications/initialized"}
                    )
                    + "\n"
                )
                process.stdin.flush()
                _exercise(rpc)
            finally:
                process.terminate()
                process.communicate(timeout=5)
        else:
            with running_server(output, TARGET_API_BASE_URL=url) as (base, _):
                headers = {"Accept": "application/json, text/event-stream"}
                index = 0

                def rpc(method: str, params: dict) -> dict:
                    nonlocal index
                    index += 1
                    response = requests.post(
                        base + "/mcp",
                        headers=headers,
                        json={
                            "jsonrpc": "2.0",
                            "id": index,
                            "method": method,
                            "params": params,
                        },
                        timeout=5,
                    )
                    assert response.status_code == 200, response.text
                    if method == "initialize":
                        headers["Mcp-Session-Id"] = response.headers["Mcp-Session-Id"]
                    return response.json()["result"]

                rpc("initialize", init)
                _exercise(rpc)
    finally:
        upstream.shutdown()
        upstream.server_close()
        thread.join(timeout=5)
