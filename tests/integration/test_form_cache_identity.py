"""Verify generated caching follows order-sensitive wire serialization."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

from click.testing import CliRunner

from openapi_to_mcp.cli import cli
from tests.integration.test_query_serialization import _build


class EchoCapture(BaseHTTPRequestHandler):
    requests: ClassVar[list[tuple[str, str]]] = []

    def do_GET(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode()
        self.requests.append((self.path, body))
        response = json.dumps(
            {"path": self.path, "body": body, "cookie": self.headers.get("Cookie")}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, _format: str, *_args: object) -> None:
        pass


def test_cache_distinguishes_actual_form_json_wire_and_auth(tmp_path: Path) -> None:
    object_schema = {
        "type": "object",
        "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
    }
    form_schema = {
        "type": "object",
        "properties": {
            "a": {"type": "string"},
            "b": {"type": "string"},
            "obj": object_schema,
        },
    }
    spec = {
        "openapi": "3.2.1",
        "info": {"title": "Cache", "version": "1"},
        "components": {
            "securitySchemes": {
                "key": {"type": "apiKey", "in": "header", "name": "X-Key"},
                "query": {"type": "apiKey", "in": "query", "name": "token"},
                "cookie": {"type": "apiKey", "in": "cookie", "name": "session"},
            }
        },
        "paths": {},
    }
    for name, content_type, schema in (
        ("form", "application/x-www-form-urlencoded", form_schema),
        ("json", "application/json", object_schema),
    ):
        spec["paths"][f"/{name}"] = {
            "get": {
                "operationId": name,
                "parameters": [
                    {
                        "name": "whole",
                        "in": "querystring",
                        "content": {content_type: {"schema": schema}},
                    }
                ],
                "security": [{"key": []}],
                "responses": {"200": {"description": "OK"}},
            }
        }
    for scheme in ("query", "cookie"):
        spec["paths"][f"/{scheme}"] = {
            "get": {
                "operationId": scheme,
                "parameters": [
                    {
                        "name": "whole",
                        "in": "querystring",
                        "content": {
                            "application/x-www-form-urlencoded": {"schema": form_schema}
                        },
                    }
                ],
                "security": [{scheme: []}],
                "responses": {"200": {"description": "OK"}},
            }
        }
    spec["paths"]["/body"] = {
        "get": {
            "operationId": "body",
            "requestBody": {
                "content": {
                    "application/x-www-form-urlencoded": {"schema": form_schema}
                }
            },
            "security": [{"key": []}],
            "responses": {"200": {"description": "OK"}},
        }
    }
    source = tmp_path / "spec.json"
    source.write_text(json.dumps(spec), encoding="utf-8")
    out = tmp_path / "generated"
    result = CliRunner().invoke(
        cli, ["generate", "-o", str(source), "-d", str(out), "--transport", "stdio"]
    )
    assert result.exit_code == 0, result.output
    _build(out)
    first = {"a": "1", "b": "2"}
    second = {"b": "2", "a": "1"}
    calls = []
    for tool, key, values in (
        ("form", "whole", [first, second]),
        ("json", "whole", [first, second]),
        ("body", "requestBody", [first, second]),
        ("form", "whole", [{"obj": first}, {"obj": second}]),
    ):
        calls.extend(
            {"tool": tool, "args": {key: value}, "token": "first-token"}
            for value in [values[0], values[1], values[0]]
        )
    calls.append({"tool": "form", "args": {"whole": first}, "token": "second-token"})
    for name in ("query", "cookie"):
        calls.extend(
            {
                "tool": name,
                "args": {"whole": first},
                "env": {f"AUTH_{name.upper()}_API_KEY": token},
            }
            for token in ("first", "first", "second")
        )
    EchoCapture.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), EchoCapture)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        node = shutil.which("node")
        assert node is not None
        env = {
            **os.environ,
            "TARGET_API_BASE_URL": f"http://127.0.0.1:{server.server_port}",
            "MCP_CACHE_TTL_MS": "60000",
        }
        script = Path(__file__).parents[1] / "resources/form_cache_identity.mjs"
        run = subprocess.run(  # noqa: S603
            [node, str(script), str(out)],
            input=json.dumps(calls),
            text=True,
            capture_output=True,
            env=env,
            check=True,
            timeout=30,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    results = json.loads(run.stdout)
    assert all(not result.get("isError", False) for result in results)
    for index in (0, 3, 6, 9):
        assert (
            results[index]["structuredContent"]
            != results[index + 1]["structuredContent"]
        )
        assert (
            results[index]["structuredContent"]
            == results[index + 2]["structuredContent"]
        )
    for index in (13, 16):
        assert (
            results[index]["structuredContent"]
            == results[index + 1]["structuredContent"]
        )
        assert (
            results[index]["structuredContent"]
            != results[index + 2]["structuredContent"]
        )
    assert len(EchoCapture.requests) == 13
