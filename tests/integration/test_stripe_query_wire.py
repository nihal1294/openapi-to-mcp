"""Characterize requests generated from the pinned Stripe fixture over MCP."""

from __future__ import annotations

import asyncio
import os
import shlex
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar
from urllib.parse import parse_qsl, urlsplit

import pytest
from click.testing import CliRunner

from openapi_to_mcp.adapters.testing import (
    ConnectionSettings,
    ServerTestRequest,
    execute_mcp_server,
)
from openapi_to_mcp.cli import cli
from tests.integration.http_health_support import running_server

FIXTURE = Path(__file__).parents[1] / "resources/compatibility_corpus/stripe.json"
LIST = "GetV2CoreEvents"
DETAIL = "GetV2CoreEventsId"
PROBE = "a+b c%2F雪/&=?#[],:;$@"
ENCODED = "a%2Bb+c%252F%E9%9B%AA%2F%26%3D%3F%23[],:%3B$%40"


class Capture(BaseHTTPRequestHandler):
    requests: ClassVar[list[tuple[str, str | None]]] = []

    def do_GET(self) -> None:
        self.requests.append((self.path, self.headers.get("Authorization")))
        body = (
            b'{"data":[],"next_page_url":null,"previous_page_url":null}'
            if self.path.split("?", 1)[0] == "/v2/core/events"
            else b'{"created":"2026-11-01T10:20:30Z","id":"evt_test",'
            b'"livemode":false,"object":"v2.core.event","type":"v2.example.created"}'
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


# The opaque strings in the encoding case are probes, not valid event types.
CASES = [
    (LIST, {}, "/v2/core/events", []),
    (
        LIST,
        {"created": {"gte": "2026-01-02T03:04:05+05:30", "lt": "2026-03-04T00:00:00Z"}},
        "/v2/core/events?created[gte]=2026-01-02T03:04:05%2B05:30&created[lt]=2026-03-04T00:00:00Z",
        [
            ("created[gte]", "2026-01-02T03:04:05+05:30"),
            ("created[lt]", "2026-03-04T00:00:00Z"),
        ],
    ),
    (LIST, {"created": {}, "types": []}, "/v2/core/events", []),
    (
        LIST,
        {"types": ["v2.example.created"]},
        "/v2/core/events?types[]=v2.example.created",
        [("types[]", "v2.example.created")],
    ),
    (
        LIST,
        {"types": ["v2.example.created", "v2.example.updated"]},
        "/v2/core/events?types[]=v2.example.created&types[]=v2.example.updated",
        [("types[]", "v2.example.created"), ("types[]", "v2.example.updated")],
    ),
    (
        LIST,
        {
            "created": {"gte": "2026-11-01T10:20:30Z"},
            "limit": 2,
            "object_id": "obj_123",
            "page": "page_1",
            "types": ["v2.example.created", "v2.example.updated"],
        },
        "/v2/core/events?created[gte]=2026-11-01T10:20:30Z&limit=2&object_id=obj_123&page=page_1&types[]=v2.example.created&types[]=v2.example.updated",
        [
            ("created[gte]", "2026-11-01T10:20:30Z"),
            ("limit", "2"),
            ("object_id", "obj_123"),
            ("page", "page_1"),
            ("types[]", "v2.example.created"),
            ("types[]", "v2.example.updated"),
        ],
    ),
    (
        LIST,
        {"object_id": PROBE, "page": PROBE, "types": [PROBE, "x y"]},
        f"/v2/core/events?object_id={ENCODED}&page={ENCODED}&types[]={ENCODED}&types[]=x+y",
        [("object_id", PROBE), ("page", PROBE), ("types[]", PROBE), ("types[]", "x y")],
    ),
    (DETAIL, {"id": "evt_123"}, "/v2/core/events/evt_123", []),
    (
        DETAIL,
        {"id": "evt_synthetic+ /?#雪"},
        "/v2/core/events/evt_synthetic%2B%20%2F%3F%23%E9%9B%AA",
        [],
    ),
]


@pytest.mark.parametrize("transport", ["stdio", "streamable-http"])
def test_stripe_query_wire(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, transport: str
) -> None:
    node = shutil.which("node")
    npm = shutil.which("npm")
    assert node, "node is required for generated wire integration tests"
    assert npm, "npm is required for generated wire integration tests"
    for key in list(os.environ):
        if key.upper().startswith(("AUTH_", "MCP_", "TARGET_API_")):
            monkeypatch.delenv(key)
    output = tmp_path / "generated"
    result = CliRunner().invoke(
        cli,
        ["generate", "-o", str(FIXTURE), "-d", str(output), "--transport", transport],
    )
    assert result.exit_code == 0, result.output
    for args in (
        ["install", "--ignore-scripts", "--no-audit", "--no-fund"],
        ["run", "build"],
    ):
        subprocess.run(  # noqa: S603
            [npm, *args],
            cwd=output,
            check=True,
            capture_output=True,
            text=True,
            timeout=180,
        )

    for key in list(os.environ):
        if key.lower().endswith("_proxy"):
            monkeypatch.delenv(key)

    Capture.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), Capture)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    env = {
        "TARGET_API_BASE_URL": f"http://127.0.0.1:{server.server_port}",
        "AUTH_BEARERAUTH_TOKEN": "synthetic_test_token",
    }

    async def exercise(connection: ConnectionSettings) -> None:
        for tool, arguments, target, pairs in CASES:
            before = len(Capture.requests)
            response = await asyncio.wait_for(
                execute_mcp_server(
                    ServerTestRequest(
                        transport,
                        "call",
                        {"tool_name": tool, "tool_arguments": arguments},
                        connection=connection,
                    )
                ),
                timeout=30,
            )
            response = response.get("result", response)
            assert response.get("isError") is False, response
            if tool == LIST:
                assert response["structuredContent"]["data"] == []
            else:
                assert response["structuredContent"]["id"] == "evt_test"
            assert len(Capture.requests) == before + 1
            actual, auth = Capture.requests[-1]
            assert auth == "Bearer synthetic_test_token"
            assert actual == target
            assert parse_qsl(urlsplit(actual).query, keep_blank_values=True) == pairs

    try:
        if transport == "stdio":
            command = (
                f"{shlex.quote(node)} {shlex.quote(str(output / 'build/index.js'))}"
            )
            asyncio.run(exercise(ConnectionSettings(server_cmd=command, env=env)))
        else:
            with running_server(output, **env) as (url, _):
                asyncio.run(exercise(ConnectionSettings(endpoint_url=url + "/mcp")))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()
