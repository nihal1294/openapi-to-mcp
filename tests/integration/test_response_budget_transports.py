"""Verify response budgets through generated MCP transports."""

from __future__ import annotations

import json
import os
import select
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, ClassVar

import pytest
import requests
from click.testing import CliRunner

from openapi_to_mcp.cli import cli
from tests.integration.basic_auth_support import basic_spec
from tests.integration.http_health_support import running_server

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(scope="module", params=["stdio", "streamable-http"])
def project(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> tuple[Path, str]:
    root = tmp_path_factory.mktemp("budget-transport")
    spec = root / "spec.json"
    spec.write_text(json.dumps(basic_spec()), encoding="utf-8")
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
        result_process = subprocess.run(  # noqa: S603
            [npm, *args],
            cwd=output,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        assert result_process.returncode == 0, (
            result_process.stdout + result_process.stderr
        )
    return output, request.param


class Upstream(BaseHTTPRequestHandler):
    body: ClassVar[bytes] = b"{}"

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


def assert_results(results: list[dict]) -> None:
    assert results[0]["structuredContent"] == {"ok": True}
    assert not results[0].get("isError", False)
    assert results[1]["isError"] is True
    assert results[1]["_meta"]["error"] == {
        "code": "response_too_large",
        "source": "upstream",
        "retryable": False,
    }
    assert (
        results[1]["content"][0]["text"]
        == "Upstream response exceeds configured byte limit."
    )
    assert "structuredContent" not in results[1]


def test_mcp_transport_response_budget(project: tuple[Path, str]) -> None:
    output, transport = project
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{upstream.server_port}"
    try:
        if transport == "stdio":
            results = call_stdio(output, base_url)
        else:
            results = call_http(output, base_url)
        assert_results(results)
    finally:
        upstream.shutdown()
        upstream.server_close()
        thread.join(timeout=5)


def call_stdio(output: Path, base_url: str) -> list[dict]:
    node = shutil.which("node")
    assert node is not None
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("MCP_", "AUTH_", "TARGET_API_"))
    }
    env.pop("FORCE_COLOR", None)
    env.pop("CLICOLOR_FORCE", None)
    env.update(
        TARGET_API_BASE_URL=base_url,
        MCP_MAX_RESPONSE_BYTES="20",
        TERM="dumb",
        NO_COLOR="1",
    )
    process = subprocess.Popen(  # noqa: S603
        [node, "build/index.js"],
        cwd=output,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    assert process.stdin is not None
    assert process.stdout is not None

    def rpc(payload: dict) -> dict:
        process.stdin.write(json.dumps(payload) + "\n")
        process.stdin.flush()
        ready, _, _ = select.select([process.stdout], [], [], 10)
        assert ready, "No MCP response received"
        line = process.stdout.readline()
        response = json.loads(line)  # Any non-protocol stdout fails here.
        assert response["id"] == payload["id"]
        return response["result"]

    try:
        rpc(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            }
        )
        process.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        )
        process.stdin.flush()
        results = []
        for index, body in enumerate(
            (b'{"ok":true}', b'{"secret":"abcdefghijklmnopqrstuvwxyz"}'), start=2
        ):
            Upstream.body = body
            results.append(
                rpc(
                    {
                        "jsonrpc": "2.0",
                        "id": index,
                        "method": "tools/call",
                        "params": {"name": "public", "arguments": {}},
                    }
                )
            )
        return results
    finally:
        process.terminate()
        remaining_stdout, _ = process.communicate(timeout=5)
        assert remaining_stdout == ""


def call_http(output: Path, base_url: str) -> list[dict]:
    with running_server(
        output, TARGET_API_BASE_URL=base_url, MCP_MAX_RESPONSE_BYTES="20"
    ) as (base, _):
        headers = {"Accept": "application/json, text/event-stream"}
        init = requests.post(
            base + "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1"},
                },
            },
            timeout=5,
        )
        assert init.status_code == 200
        headers["Mcp-Session-Id"] = init.headers["Mcp-Session-Id"]
        results = []
        for index, body in enumerate(
            (b'{"ok":true}', b'{"secret":"abcdefghijklmnopqrstuvwxyz"}'), start=2
        ):
            Upstream.body = body
            response = requests.post(
                base + "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": index,
                    "method": "tools/call",
                    "params": {"name": "public", "arguments": {}},
                },
                timeout=5,
            )
            assert response.status_code == 200
            results.append(response.json()["result"])
        return results
