"""Exercise OpenAPI 3.2 operations through generated MCP transports."""

import asyncio
import json
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, ClassVar

import pytest
from click.testing import CliRunner

from openapi_to_mcp.adapters.testing import (
    ConnectionSettings,
    ServerTestRequest,
    execute_mcp_server,
)
from openapi_to_mcp.cli import cli
from tests.integration.http_health_support import running_server

if TYPE_CHECKING:
    from pathlib import Path


class Capture(BaseHTTPRequestHandler):
    requests: ClassVar[list] = []

    def capture(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.requests.append(
            (self.command, self.path, dict(self.headers), json.loads(body))
        )
        response = b'{"ok":true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    do_QUERY = capture  # noqa: N815
    do_COPY = capture  # noqa: N815
    do_PROPFIND = capture  # noqa: N815

    def log_message(self, *_args: object) -> None:
        pass


@pytest.mark.parametrize("transport", ["stdio", "streamable-http"])
def test_wire_methods_and_request_data(tmp_path: Path, transport: str) -> None:
    operation = {
        "parameters": [
            {
                "name": "id",
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
            },
            {"name": "q", "in": "query", "schema": {"type": "string"}},
            {"name": "X-Test", "in": "header", "schema": {"type": "string"}},
            {"name": "session", "in": "cookie", "schema": {"type": "string"}},
        ],
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"value": {"type": "string"}},
                    }
                }
            },
        },
        "responses": {"200": {"description": "OK"}},
    }
    spec = {
        "openapi": "3.2.1",
        "info": {"title": "Methods", "version": "1"},
        "servers": [{"url": "https://example.com"}],
        "security": [{"Key": []}],
        "components": {
            "securitySchemes": {
                "Key": {"type": "apiKey", "in": "header", "name": "X-Api-Key"}
            }
        },
        "paths": {
            "/items/{id}": {
                "query": {**operation, "operationId": "queryItems"},
                "additionalOperations": {
                    m: {**operation, "operationId": m.lower() + "Items"}
                    for m in ("COPY", "PROPFIND")
                },
            }
        },
    }
    source = tmp_path / "spec.json"
    source.write_text(json.dumps(spec))
    output = tmp_path / "generated"
    result = CliRunner().invoke(
        cli,
        ["generate", "-o", str(source), "-d", str(output), "--transport", transport],
    )
    assert result.exit_code == 0, result.output
    npm = shutil.which("npm")
    assert npm
    for args in (
        ["install", "--ignore-scripts", "--no-audit", "--no-fund"],
        ["run", "build"],
    ):
        result = subprocess.run(  # noqa: S603
            [npm, *args],
            cwd=output,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    Capture.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), Capture)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    env = {
        "TARGET_API_BASE_URL": f"http://127.0.0.1:{server.server_port}",
        "AUTH_KEY_API_KEY": "secret",
    }

    async def call(connection, method):
        return await execute_mcp_server(
            ServerTestRequest(
                transport,
                "call",
                {
                    "tool_name": method.lower() + "Items",
                    "tool_arguments": {
                        "id": "42",
                        "q": "a b",
                        "X-Test": "header",
                        "session": "cookie",
                        "requestBody": {"value": "payload"},
                    },
                },
                connection=connection,
            )
        )

    try:
        if transport == "stdio":
            connection = ConnectionSettings(
                server_cmd=f"node {output / 'build' / 'index.js'}", env=env
            )
            for method in ("QUERY", "COPY", "PROPFIND"):
                assert not asyncio.run(call(connection, method)).get("isError", False)
        else:
            with running_server(output, **env) as (base, _):
                connection = ConnectionSettings(endpoint_url=base + "/mcp")
                for method in ("QUERY", "COPY", "PROPFIND"):
                    assert not asyncio.run(call(connection, method)).get(
                        "isError", False
                    )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    assert len(Capture.requests) == 3
    for request, method in zip(
        Capture.requests, ("QUERY", "COPY", "PROPFIND"), strict=True
    ):
        actual, path, headers, body = request
        assert actual == method
        assert path == "/items/42?q=a+b"
        assert headers["X-Test"] == "header"
        assert headers["Cookie"] == "session=cookie"
        assert headers["X-Api-Key"] == "secret"
        assert body == {"value": "payload"}
