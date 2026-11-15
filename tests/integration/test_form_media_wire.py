"""Raw generated wire tests for whole query and form bodies."""

from __future__ import annotations

import asyncio
import json
import os
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
from tests.integration.basic_auth_support import run_auth_case
from tests.integration.http_health_support import running_server
from tests.integration.test_query_serialization import _build

if TYPE_CHECKING:
    from pathlib import Path


class Capture(BaseHTTPRequestHandler):
    requests: ClassVar[list[tuple[str, str, str]]] = []

    def do_POST(self) -> None:
        data = self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode()
        self.requests.append((self.path, data, self.headers.get("Content-Type", "")))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")

    def do_GET(self) -> None:
        data = self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode()
        self.requests.append((self.path, data, self.headers.get("Content-Type", "")))
        self.send_response(
            503
            if sum(path.startswith("/retry") for path, _, _ in self.requests) == 1
            else 200
        )
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, _format: str, *_args: object) -> None:
        pass


@pytest.mark.parametrize("transport", ["stdio", "streamable-http"])
def test_form_query_and_body_wire(tmp_path: Path, transport: str) -> None:  # noqa: PLR0915
    schema = {
        "type": "object",
        "properties": {
            "a": {"type": "string"},
            "__proto__": {"type": "string"},
            "constructor": {"type": "string"},
            "empty": {"type": "string"},
            "falseFlag": {"type": "string"},
            "jsonField": {"type": "string"},
            "nil": {"type": "string"},
            "emptyTags": {"type": "array", "items": {"type": "string"}},
            "flat": {
                "type": "object",
                "properties": {"p": {"type": "string"}, "q": {"type": "string"}},
            },
            "open": {"type": "object", "properties": {"u": {"type": "string"}}},
            "tags": {"type": "array", "items": {"type": "string"}},
            "obj": {"type": "object", "properties": {"x": {"type": "string"}}},
        },
    }
    media = {
        "schema": schema,
        "encoding": {
            "tags": {"explode": False},
            "falseFlag": {"allowReserved": False, "contentType": "application/json"},
            "jsonField": {"contentType": "application/json"},
            "flat": {"style": "form", "explode": False},
            "open": {"style": "form", "explode": True},
        },
    }
    spec = {
        "openapi": "3.2.1",
        "info": {"title": "Wire", "version": "1"},
        "paths": {
            "/send": {
                "post": {
                    "operationId": "send",
                    "parameters": [
                        {
                            "name": "whole",
                            "in": "querystring",
                            "required": True,
                            "content": {"application/x-www-form-urlencoded": media},
                        }
                    ],
                    "requestBody": {
                        "content": {"application/x-www-form-urlencoded": media}
                    },
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    spec["components"] = {
        "securitySchemes": {
            "key": {"type": "apiKey", "in": "query", "name": "a"},
            "token": {"type": "apiKey", "in": "query", "name": "token"},
            "expanded": {"type": "apiKey", "in": "query", "name": "x"},
        }
    }
    for name, content_type, value_schema, security in (
        ("collision", "application/x-www-form-urlencoded", media, "key"),
        ("safe", "application/x-www-form-urlencoded", media, "token"),
        ("opaque", "application/json", {"schema": {"type": "object"}}, "token"),
    ):
        spec["paths"][f"/{name}"] = {
            "post": {
                "operationId": name,
                "parameters": [
                    {
                        "name": "whole",
                        "in": "querystring",
                        "content": {content_type: value_schema},
                    }
                ],
                "security": [{security: []}],
                "responses": {"200": {"description": "OK"}},
            }
        }
    spec["paths"]["/retry"] = {
        "get": {
            "operationId": "retry",
            "parameters": [
                {
                    "name": "whole",
                    "in": "querystring",
                    "content": {"application/x-www-form-urlencoded": media},
                }
            ],
            "requestBody": {"content": {"application/x-www-form-urlencoded": media}},
            "responses": {"200": {"description": "OK"}},
        }
    }
    expanded_media = {
        "schema": schema,
        "encoding": {"obj": {"style": "form", "explode": True}},
    }
    spec["paths"]["/expanded"] = {
        "post": {
            "operationId": "expanded",
            "parameters": [
                {
                    "name": "whole",
                    "in": "querystring",
                    "content": {"application/x-www-form-urlencoded": expanded_media},
                }
            ],
            "security": [{"expanded": []}],
            "responses": {"200": {"description": "OK"}},
        }
    }
    spec["paths"]["/ordinary"] = {
        "post": {
            "operationId": "ordinary",
            "security": [{"token": []}],
            "responses": {"200": {"description": "OK"}},
        }
    }
    for name, content_type, field_schema in (
        ("jsonquery", "application/json", {"type": "object"}),
        ("textquery", "text/plain", {"type": "string"}),
    ):
        spec["paths"][f"/{name}"] = {
            "post": {
                "operationId": name,
                "parameters": [
                    {
                        "name": "whole",
                        "in": "querystring",
                        "content": {content_type: {"schema": field_schema}},
                    }
                ],
                "responses": {"200": {"description": "OK"}},
            }
        }
    source = tmp_path / "spec.json"
    source.write_text(json.dumps(spec), encoding="utf-8")
    out = tmp_path / "generated"
    result = CliRunner().invoke(
        cli,
        [
            "generate",
            "-o",
            str(source),
            "-d",
            str(out),
            "--transport",
            transport,
            "--runtime-validation",
            "none",
        ],
    )
    assert result.exit_code == 0, result.output
    _build(out)
    axios_version = os.environ.get("FORM_TEST_AXIOS_VERSION")
    if axios_version:
        npm = shutil.which("npm")
        assert npm is not None
        subprocess.run(  # noqa: S603
            [npm, "install", "--no-save", "--ignore-scripts", f"axios@{axios_version}"],
            cwd=out,
            check=True,
        )
        subprocess.run([npm, "run", "build"], cwd=out, check=True)  # noqa: S603
    if transport == "stdio":
        capture, logs = run_auth_case(
            out,
            {
                "tool": "send",
                "arguments": {
                    "whole": {"a": "whole-secret"},
                    "requestBody": {"obj": {"x": "body-secret"}},
                },
                "env": {"MCP_AUDIT_REDACT_REQUEST_BODY_PATHS": "obj.x"},
            },
        )
        assert not capture["result"].get("isError", False)
        audit = [json.loads(line) for line in logs.splitlines() if line.startswith("{")]
        request = next(
            event for event in audit if event["event"] == "tool_audit_request"
        )
        assert request["query"] == "[REDACTED]"
        assert request["targetPath"] == "/send"
        assert request["requestBody"]["obj"]["x"] == "[REDACTED]"
        assert "whole-secret" not in logs
        assert "body-secret" not in logs
        capture, logs = run_auth_case(
            out, {"tool": "ordinary", "env": {"AUTH_TOKEN_API_KEY": "query-secret"}}
        )
        assert not capture["result"].get("isError", False)
        audit = [json.loads(line) for line in logs.splitlines() if line.startswith("{")]
        request = next(
            event for event in audit if event["event"] == "tool_audit_request"
        )
        assert request["query"]["token"] == "[REDACTED]"  # noqa: S105
        assert "query-secret" not in logs
    Capture.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), Capture)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        value = {
            "a": "é +%&=",
            "__proto__": "own value",
            "constructor": "ordinary",
            "empty": "",
            "falseFlag": "a b",
            "jsonField": "a b",
            "nil": None,
            "emptyTags": [],
            "flat": {"p": "a,b", "q": "x +"},
            "open": {"u": "a&b"},
            "tags": ["a b", "c,d"],
            "obj": {"x": "a+b"},
        }

        async def call(
            connection: ConnectionSettings, name: str, arguments: dict
        ) -> dict:
            result = await execute_mcp_server(
                ServerTestRequest(
                    transport,
                    "call",
                    {"tool_name": name, "tool_arguments": arguments},
                    connection=connection,
                )
            )
            return result.get("result", result)

        base = f"http://127.0.0.1:{server.server_port}"

        async def exercise(connection: ConnectionSettings) -> None:
            result = await call(
                connection, "send", {"whole": value, "requestBody": value}
            )
            assert not result.get("isError", False), result
            for name, arguments in (
                ("send", {}),
                ("send", {"whole": None}),
                ("send", {"whole": {"unknown": "secret"}}),
                ("send", {"whole": {"flat": {"unknown": "secret"}}}),
                ("collision", {"whole": {"a": "secret"}}),
                ("opaque", {"whole": {"secret": "value"}}),
                ("expanded", {"whole": {"obj": {"x": "secret"}}}),
            ):
                failure = await call(connection, name, arguments)
                assert failure.get("isError") is True, failure
                assert "secret" not in json.dumps(failure)
            empty = await call(connection, "send", {"whole": {}})
            assert not empty.get("isError", False), empty
            empty_text = await call(connection, "textquery", {"whole": ""})
            assert not empty_text.get("isError", False), empty_text
            json_result = await call(
                connection, "jsonquery", {"whole": {"x": "é +%&="}}
            )
            assert not json_result.get("isError", False), json_result
            text_result = await call(connection, "textquery", {"whole": "é +%&="})
            assert not text_result.get("isError", False), text_result
            retry = await call(
                connection, "retry", {"whole": value, "requestBody": value}
            )
            assert not retry.get("isError", False), retry
            safe = await call(connection, "safe", {"whole": {"a": "value"}})
            assert not safe.get("isError", False), safe

        env = {
            "TARGET_API_BASE_URL": base,
            "AUTH_KEY_API_KEY": "private-key",
            "AUTH_TOKEN_API_KEY": "private-token",
            "AUTH_EXPANDED_API_KEY": "private-expanded",
            "MCP_RETRY_MAX_RETRIES": "1",
            "MCP_RETRY_BUDGET_PER_MINUTE": "5",
        }
        if transport == "stdio":
            asyncio.run(
                exercise(
                    ConnectionSettings(
                        server_cmd=f"node {out / 'build' / 'index.js'}", env=env
                    )
                )
            )
            for delimiter in ("?", "#"):
                bad_env = {**env, "TARGET_API_BASE_URL": base + delimiter}
                failure = asyncio.run(
                    call(
                        ConnectionSettings(
                            server_cmd=f"node {out / 'build' / 'index.js'}", env=bad_env
                        ),
                        "send",
                        {"whole": {"a": "secret"}},
                    )
                )
                assert failure.get("isError") is True
                assert "secret" not in json.dumps(failure)
        else:
            with running_server(out, **env) as (url, _):
                asyncio.run(exercise(ConnectionSettings(endpoint_url=url + "/mcp")))

    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    wire = "a=%C3%A9+%2B%25%26%3D&__proto__=own+value&constructor=ordinary&empty=&falseFlag=a%20b&jsonField=%22a+b%22&flat=p,a%2Cb,q,x%20%2B&u=a%26b&tags=a%20b&tags=c%2Cd&obj=%7B%22x%22%3A%22a%2Bb%22%7D"
    assert Capture.requests == [
        (f"/send?{wire}", wire, "application/x-www-form-urlencoded"),
        ("/send", "", "application/x-www-form-urlencoded"),
        ("/textquery", "", "application/x-www-form-urlencoded"),
        (
            "/jsonquery?%7B%22x%22%3A%22%C3%A9%20%2B%25%26%3D%22%7D",
            "",
            "application/x-www-form-urlencoded",
        ),
        ("/textquery?%C3%A9%20%2B%25%26%3D", "", "application/x-www-form-urlencoded"),
        (f"/retry?{wire}", wire, "application/x-www-form-urlencoded"),
        (f"/retry?{wire}", wire, "application/x-www-form-urlencoded"),
        ("/safe?a=value&token=private-token", "", "application/x-www-form-urlencoded"),
    ]


@pytest.mark.parametrize("version", ["3.0.4", "3.1.2"])
def test_earlier_form_array_style_wire(tmp_path: Path, version: str) -> None:
    media = {
        "schema": {
            "type": "object",
            "properties": {
                "tags": {"type": "array", "items": {"type": "string"}},
                "plain": {"type": "array", "items": {"type": "string"}},
            },
        },
        "encoding": {"tags": {"explode": False}},
    }
    spec = {
        "openapi": version,
        "info": {"title": "Wire", "version": "1"},
        "paths": {
            "/send": {
                "post": {
                    "operationId": "send",
                    "requestBody": {
                        "content": {"application/x-www-form-urlencoded": media}
                    },
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    source = tmp_path / "spec.json"
    source.write_text(json.dumps(spec), encoding="utf-8")
    out = tmp_path / "generated"
    result = CliRunner().invoke(
        cli, ["generate", "-o", str(source), "-d", str(out), "--transport", "stdio"]
    )
    assert result.exit_code == 0, result.output
    _build(out)
    Capture.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), Capture)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = ConnectionSettings(
            server_cmd=f"node {out / 'build' / 'index.js'}",
            env={"TARGET_API_BASE_URL": f"http://127.0.0.1:{server.server_port}"},
        )
        result = asyncio.run(
            execute_mcp_server(
                ServerTestRequest(
                    "stdio",
                    "call",
                    {
                        "tool_name": "send",
                        "tool_arguments": {
                            "requestBody": {
                                "tags": ["a b", "c,d"],
                                "plain": ["a b", "c+d"],
                            }
                        },
                    },
                    connection=connection,
                )
            )
        )
        assert not result.get("isError", False), result
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    assert Capture.requests == [
        (
            "/send",
            "tags=a%20b,c%2Cd&plain=a+b&plain=c%2Bd",
            "application/x-www-form-urlencoded",
        )
    ]


def test_prototype_names_with_input_validation(tmp_path: Path) -> None:
    spec = {
        "openapi": "3.2.1",
        "info": {"title": "Wire", "version": "1"},
        "components": {
            "schemas": {
                "Form": {
                    "type": "object",
                    "properties": {
                        "__proto__": {"type": "string"},
                        "constructor": {"type": "string"},
                    },
                }
            }
        },
        "paths": {
            "/send": {
                "post": {
                    "operationId": "send",
                    "parameters": [
                        {
                            "name": "whole",
                            "in": "querystring",
                            "content": {
                                "application/x-www-form-urlencoded": {
                                    "schema": {"$ref": "#/components/schemas/Form"}
                                }
                            },
                        }
                    ],
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    source = tmp_path / "spec.json"
    source.write_text(json.dumps(spec), encoding="utf-8")
    out = tmp_path / "generated"
    result = CliRunner().invoke(
        cli, ["generate", "-o", str(source), "-d", str(out), "--transport", "stdio"]
    )
    assert result.exit_code == 0, result.output
    _build(out)
    Capture.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), Capture)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = ConnectionSettings(
            server_cmd=f"node {out / 'build' / 'index.js'}",
            env={"TARGET_API_BASE_URL": f"http://127.0.0.1:{server.server_port}"},
        )
        result = asyncio.run(
            execute_mcp_server(
                ServerTestRequest(
                    "stdio",
                    "call",
                    {
                        "tool_name": "send",
                        "tool_arguments": {
                            "whole": {"__proto__": "safe", "constructor": "value"}
                        },
                    },
                    connection=connection,
                )
            )
        )
        assert not result.get("isError", False), result
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    assert Capture.requests == [
        (
            "/send?__proto__=safe&constructor=value",
            "",
            "application/x-www-form-urlencoded",
        )
    ]


@pytest.mark.parametrize("transport", ["stdio", "streamable-http"])
def test_ordinary_json_and_text_bodies_wire(tmp_path: Path, transport: str) -> None:
    paths = {}
    for name, media_type, schema in (
        ("jsonbody", "application/json", {"type": "object"}),
        ("textbody", "text/plain", {"type": "string"}),
    ):
        paths[f"/{name}"] = {
            "post": {
                "operationId": name,
                "requestBody": {
                    "required": True,
                    "content": {media_type: {"schema": schema}},
                },
                "responses": {"200": {"description": "OK"}},
            }
        }
    spec = {
        "openapi": "3.1.2",
        "info": {"title": "Wire", "version": "1"},
        "paths": paths,
    }
    source = tmp_path / "spec.json"
    source.write_text(json.dumps(spec), encoding="utf-8")
    out = tmp_path / "generated"
    result = CliRunner().invoke(
        cli, ["generate", "-o", str(source), "-d", str(out), "--transport", transport]
    )
    assert result.exit_code == 0, result.output
    _build(out)
    Capture.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), Capture)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:

        async def exercise(connection: ConnectionSettings) -> None:
            for name, body in (
                ("jsonbody", {"a": "é +%&=", "n": 2}),
                ("textbody", "é +%&="),
            ):
                result = await execute_mcp_server(
                    ServerTestRequest(
                        transport,
                        "call",
                        {"tool_name": name, "tool_arguments": {"requestBody": body}},
                        connection=connection,
                    )
                )
                result = result.get("result", result)
                assert not result.get("isError", False), result

        env = {"TARGET_API_BASE_URL": f"http://127.0.0.1:{server.server_port}"}
        if transport == "stdio":
            asyncio.run(
                exercise(
                    ConnectionSettings(
                        server_cmd=f"node {out / 'build' / 'index.js'}", env=env
                    )
                )
            )
        else:
            with running_server(out, **env) as (url, _):
                asyncio.run(exercise(ConnectionSettings(endpoint_url=url + "/mcp")))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    assert Capture.requests == [
        ("/jsonbody", '{"a":"é +%&=","n":2}', "application/json"),
        ("/textbody", "é +%&=", "text/plain"),
    ]
