"""Exercise modern MCP wire behavior on generated transports."""

import json
import os
import select
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import requests
from click.testing import CliRunner

from openapi_to_mcp.cli import cli
from tests.integration.http_health_support import running_server
from tests.integration.test_query_serialization import _build

META = {
    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
    "io.modelcontextprotocol/clientCapabilities": {},
    "io.modelcontextprotocol/clientInfo": {"name": "wire-test", "version": "1"},
}


@pytest.fixture(scope="module", params=["stdio", "streamable-http"])
def generated(request, tmp_path_factory) -> tuple[str, Path]:
    out = tmp_path_factory.mktemp("modern") / "server"
    spec = Path(__file__).parents[2] / "examples/container/openapi.yaml"
    result = CliRunner().invoke(
        cli, ["generate", "-o", str(spec), "-d", str(out), "-t", request.param]
    )
    assert result.exit_code == 0, result.output
    _build(out)
    subprocess.run(
        [  # noqa: S607
            "npm",
            "install",
            "--no-save",
            "--ignore-scripts",
            "--no-audit",
            "--no-fund",
            "@modelcontextprotocol/client@2.4.0",
        ],
        cwd=out,
        check=True,
        capture_output=True,
    )
    return request.param, out


def message(method, params=None, ident=1) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": ident,
        "method": method,
        "params": {"_meta": META, **(params or {})},
    }


class Upstream(BaseHTTPRequestHandler):
    calls = 0
    active = 0
    peak = 0
    lock = threading.Lock()

    def do_GET(self) -> None:
        with self.lock:
            type(self).calls += 1
            type(self).active += 1
            type(self).peak = max(type(self).peak, type(self).active)
            count = type(self).calls
        time.sleep(0.15)
        body = json.dumps({"id": str(count), "source": "synthetic"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        with self.lock:
            type(self).active -= 1

    def log_message(self, *args) -> None:
        pass


def test_modern_wire(generated) -> None:
    transport, out = generated
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()
    env = {
        "TARGET_API_BASE_URL": f"http://127.0.0.1:{upstream.server_port}",
        "AUTH_DEMO_API_KEY": "test",
    }
    try:
        if transport == "stdio":
            proc = subprocess.Popen(  # noqa: S603
                ["node", str(out / "build/index.js")],  # noqa: S607
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env={**os.environ, **env},
                text=True,
                bufsize=1,
            )
            try:

                def send(body):
                    proc.stdin.write(json.dumps(body) + "\n")
                    proc.stdin.flush()
                    assert select.select([proc.stdout], [], [], 10)[0]
                    return json.loads(proc.stdout.readline())

                _exercise(send)
            finally:
                proc.stdin.close()
                proc.wait(timeout=10)
            _sdk_clients(out, "stdio", env)
        else:
            with running_server(out, **env) as (base, _):

                def send(body, version="2026-07-28"):
                    headers = {
                        "MCP-Protocol-Version": version,
                        "Mcp-Method": body["method"],
                        "Accept": "application/json, text/event-stream",
                    }
                    if body["method"] == "tools/call":
                        headers["Mcp-Name"] = body["params"]["name"]
                    response = requests.post(
                        base + "/mcp", json=body, headers=headers, timeout=10
                    )
                    return response.json()

                _exercise(send)
                _check_http_body_errors(base)
                mismatch = message("tools/list")
                mismatch["params"]["_meta"] = {
                    **META,
                    "io.modelcontextprotocol/protocolVersion": "2025-11-25",
                }
                assert send(mismatch)["error"]["code"] == -32020
                unsupported = message("tools/list")
                unsupported["params"]["_meta"] = {
                    **META,
                    "io.modelcontextprotocol/protocolVersion": "2099-01-01",
                }
                error = send(unsupported, "2099-01-01")["error"]
                assert error["code"] == -32022
                assert "2026-07-28" in error["data"]["supported"]
                _sdk_clients(out, base + "/mcp", env)
                _check_lifecycle(out, env)
    finally:
        upstream.shutdown()
        upstream.server_close()
        thread.join(timeout=5)


def _check_http_body_errors(base: str) -> None:
    headers = {
        "Content-Type": "application/json",
        "MCP-Protocol-Version": "2026-07-28",
        "Mcp-Method": "tools/list",
        "Accept": "application/json, text/event-stream",
    }
    malformed = requests.post(base + "/mcp", data="{", headers=headers, timeout=10)
    assert malformed.status_code == 400
    assert malformed.json()["error"]["code"] == -32700
    assert "SyntaxError" not in malformed.text
    large = requests.post(
        base + "/mcp",
        data=b"x" * (1024 * 1024 + 1),
        headers={**headers, "Content-Type": "text/plain"},
        timeout=10,
    )
    assert large.status_code == 413
    assert large.json()["error"]["code"] == -32000
    large_json = requests.post(
        base + "/mcp", data=b" " * (1024 * 1024 + 1), headers=headers, timeout=10
    )
    assert large_json.status_code == 413
    assert large_json.json()["error"]["code"] == -32000
    wrong_type = requests.post(
        base + "/mcp",
        data="{}",
        headers={**headers, "Content-Type": "text/plain"},
        timeout=10,
    )
    assert wrong_type.status_code == 415
    assert wrong_type.json()["error"]["code"] == -32000


def _sdk_clients(out: Path, endpoint: str, env: dict[str, str]) -> None:
    script = out / "sdk-client-check.mjs"
    script.write_text("""
import { Client, StreamableHTTPClientTransport } from '@modelcontextprotocol/client';
import { StdioClientTransport } from '@modelcontextprotocol/client/stdio';
for (const mode of ['legacy', 'auto', { pin: '2026-07-28' }]) {
  const client = new Client({ name: 'integration-test', version: '1' }, { versionNegotiation: { mode } });
  const transport = process.argv[2] === 'stdio'
    ? new StdioClientTransport({ command: process.execPath, args: ['build/index.js'], env: process.env, stderr: 'pipe' })
    : new StreamableHTTPClientTransport(new URL(process.argv[2]));
  try {
    await client.connect(transport);
    const listing = await client.listTools();
    if (listing.tools.length !== 1 || listing.tools[0].name !== 'getWidget') throw Error('tool list mismatch');
    const result = await client.callTool({ name: 'getWidget', arguments: { widgetId: 'sdk' } });
    if (result.isError || result.structuredContent.source !== 'synthetic') throw Error('tool call mismatch');
    if (client.getServerCapabilities()?.resources) throw Error('unexpected resources capability');
  } finally { await client.close(); }
}
""")
    subprocess.run(  # noqa: S603
        ["node", str(script), endpoint],  # noqa: S607
        cwd=out,
        env={**os.environ, **env},
        check=True,
        capture_output=True,
        text=True,
        timeout=45,
    )


def _check_lifecycle(out: Path, env: dict[str, str]) -> None:
    script = out / "lifecycle-check.mjs"
    script.write_text("""
import { createMcpHandler } from '@modelcontextprotocol/server';
import { OpenApiMcpServer } from './build/server.js';
const handler = createMcpHandler(() => new OpenApiMcpServer().server);
for (let i = 0; i < 20; i++) {
  const body = { jsonrpc: '2.0', id: i, method: 'tools/list', params: { _meta: {
    'io.modelcontextprotocol/protocolVersion': '2026-07-28',
    'io.modelcontextprotocol/clientCapabilities': {},
    'io.modelcontextprotocol/clientInfo': { name: 'test', version: '1' }
  } } };
  const response = await handler.fetch(new Request('http://localhost/mcp', {
    method: 'POST', headers: { 'content-type': 'application/json', accept: 'application/json, text/event-stream',
      'MCP-Protocol-Version': '2026-07-28', 'Mcp-Method': 'tools/list' }, body: JSON.stringify(body)
  }));
  if (!response.ok || !(await response.json()).result) throw Error('request failed');
}
await new Promise(resolve => setTimeout(resolve, 0));
if (OpenApiMcpServer.activeInstances.size !== 0) throw Error('protocol servers retained after close');
""")
    subprocess.run(  # noqa: S603
        ["node", str(script)],  # noqa: S607
        cwd=out,
        env={**os.environ, **env},
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )


def _exercise(send):
    discover = send(message("server/discover"))["result"]
    assert "2026-07-28" in discover["supportedVersions"]
    assert discover["resultType"] == "complete"
    listing = send(message("tools/list"))["result"]
    assert listing["resultType"] == "complete"
    assert listing["ttlMs"] == 0
    assert listing["cacheScope"] == "private"
    assert [tool["name"] for tool in listing["tools"]] == ["getWidget"]
    result = send(
        message("tools/call", {"name": "getWidget", "arguments": {"widgetId": "x"}})
    )["result"]
    assert result["resultType"] == "complete"
    assert result["structuredContent"]["source"] == "synthetic"
    assert "error" in send(message("resources/list"))


def test_modern_http_shared_limits_and_caller_cache(generated) -> None:
    transport, out = generated
    if transport != "streamable-http":
        pytest.skip("HTTP-specific request isolation")
    Upstream.calls = Upstream.active = Upstream.peak = 0
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()
    try:
        with running_server(
            out,
            TARGET_API_BASE_URL=f"http://127.0.0.1:{upstream.server_port}",
            AUTH_DEMO_API_KEY="test",
            MCP_CACHE_TTL_MS="60000",
            MCP_MAX_CONCURRENCY="1",
            MCP_TOOL_IDENTITY_HEADER="x-caller",
            MCP_TOOL_ACCESS_MODE="allowlist",
            MCP_TOOL_ACCESS_DEFAULT="deny",
            MCP_TOOL_ALLOWLISTS=json.dumps(
                {"alice": ["getWidget"], "bob": ["getWidget"], "denied": []}
            ),
        ) as (base, _):

            def call(identity, method="tools/call", widget="x"):
                params = (
                    {"name": "getWidget", "arguments": {"widgetId": widget}}
                    if method == "tools/call"
                    else {}
                )
                headers = {
                    "MCP-Protocol-Version": "2026-07-28",
                    "Mcp-Method": method,
                    "Accept": "application/json, text/event-stream",
                    "x-caller": identity,
                }
                if method == "tools/call":
                    headers["Mcp-Name"] = "getWidget"
                return requests.post(
                    base + "/mcp",
                    json=message(method, params),
                    headers=headers,
                    timeout=10,
                ).json()["result"]

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(call, ["alice", "bob"]))
            assert Upstream.peak == 1
            assert Upstream.calls == 2
            assert (
                results[0]["structuredContent"]["id"]
                != results[1]["structuredContent"]["id"]
            )
            assert call("alice")["structuredContent"] == results[0]["structuredContent"]
            assert Upstream.calls == 2
            with ThreadPoolExecutor(max_workers=2) as pool:
                lists = list(
                    pool.map(lambda who: call(who, "tools/list"), ["alice", "denied"])
                )
            assert len(lists[0]["tools"]) == 1
            assert lists[1]["tools"] == []
    finally:
        upstream.shutdown()
        upstream.server_close()
        thread.join(timeout=5)


def test_stdio_readiness_and_startup_failure(tmp_path: Path) -> None:
    out = tmp_path / "server"
    spec = Path(__file__).parents[2] / "examples/container/openapi.yaml"
    result = CliRunner().invoke(
        cli, ["generate", "-o", str(spec), "-d", str(out), "-t", "stdio"]
    )
    assert result.exit_code == 0, result.output
    _build(out)
    env = {
        **os.environ,
        "TARGET_API_BASE_URL": "http://127.0.0.1:9",
        "AUTH_DEMO_API_KEY": "test",
    }
    ready = subprocess.run(
        ["node", "build/index.js"],  # noqa: S607
        cwd=out,
        input="",
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
        check=False,
    )
    assert ready.returncode == 0, ready.stderr
    assert "MCP_SERVER_READY" in ready.stderr
    startup_script = """import { StdioServerTransport } from '@modelcontextprotocol/server/stdio';
StdioServerTransport.prototype.start = async () => { throw Error('synthetic startup failure'); };
await import('./build/index.js');
"""
    failure = subprocess.run(  # noqa: S603
        ["node", "--input-type=module", "-e", startup_script],  # noqa: S607
        cwd=out,
        input="",
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
        check=False,
    )
    assert failure.returncode != 0
    assert "MCP_SERVER_READY" not in failure.stderr
    assert "synthetic startup failure" in failure.stderr
    (out / "build/custom/tools.js").write_text(
        "export function getCustomTools() { return [{tool: {name: 'getWidget'}}]; }\n"
    )
    invalid = subprocess.run(
        ["node", "build/index.js"],  # noqa: S607
        cwd=out,
        input="",
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
        check=False,
    )
    assert invalid.returncode != 0
    assert "MCP_SERVER_READY" not in invalid.stderr
    assert "conflicts with a generated tool" in invalid.stderr
