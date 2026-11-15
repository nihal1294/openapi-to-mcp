"""Exercise process-wide telemetry shutdown on a normal stdio EOF."""

from __future__ import annotations

import json
import os
import select
import shutil
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(scope="module")
def eof_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("telemetry-eof") / "server"
    generated = CliRunner().invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            "examples/container/openapi.yaml",
            "--output-dir",
            str(output),
            "--transport",
            "stdio",
            "--telemetry",
            "opentelemetry",
        ],
    )
    assert generated.exit_code == 0, generated.output
    (output / "src/custom/tools.ts").write_text("""
import type { CustomToolDefinition } from '../runtime/generated.js';
export function getCustomTools(): CustomToolDefinition[] {
  return [{ tool: { name: 'eof_tool', description: 'test', inputSchema: { type: 'object', properties: {} } }, handler: async () => ({ content: [{ type: 'text', text: 'ok' }] }) }];
}
""")
    (output / "shutdown-probe.mjs").write_text("""
import { NodeSDK } from '@opentelemetry/sdk-node';
import { appendFileSync } from 'node:fs';
const original = NodeSDK.prototype.shutdown;
NodeSDK.prototype.shutdown = function (...args) {
  appendFileSync(process.env.TEST_SHUTDOWN_MARKER, 'called\\n');
  return original.apply(this, args);
};
""")
    npm = shutil.which("npm")
    assert npm
    for command in (
        [npm, "install", "--ignore-scripts", "--no-audit", "--no-fund"],
        [npm, "run", "build"],
    ):
        subprocess.run(command, cwd=output, check=True, capture_output=True, text=True)  # noqa: S603
    return output


@pytest.mark.parametrize("mode", ["success", "unavailable", "hanging", "off"])
def test_stdio_eof_flushes_or_finishes_bounded(  # noqa: C901, PLR0915
    eof_project: Path, tmp_path: Path, mode: str
) -> None:
    payloads: list[tuple[str, dict]] = []

    class Collector(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
                parts = []
                while True:
                    size = int(self.rfile.readline().strip().split(b";")[0], 16)
                    if not size:
                        self.rfile.readline()
                        break
                    parts.append(self.rfile.read(size))
                    self.rfile.read(2)
                body = b"".join(parts)
            else:
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            payloads.append((self.path, json.loads(body)))
            if mode == "hanging":
                time.sleep(4)
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *_args: object) -> None:
            pass

    collector = ThreadingHTTPServer(("127.0.0.1", 0), Collector)
    collector.daemon_threads = True
    port = collector.server_port
    if mode == "unavailable":
        collector.server_close()
    else:
        threading.Thread(target=collector.serve_forever, daemon=True).start()
    marker = tmp_path / "shutdown-observed"
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("MCP_", "OTEL_", "AUTH_", "TARGET_API_"))
    }
    env.update(
        {
            "MCP_OTEL_ENABLED": "off" if mode == "off" else "on",
            "MCP_OTEL_EXPORTER_OTLP_ENDPOINT": f"http://127.0.0.1:{port}/base",
            "TARGET_API_BASE_URL": "http://127.0.0.1:9",
            "NODE_OPTIONS": f"--import={eof_project / 'shutdown-probe.mjs'}",
            "TEST_SHUTDOWN_MARKER": str(marker),
        }
    )
    node = shutil.which("node")
    assert node
    process = subprocess.Popen(  # noqa: S603
        [node, "build/index.js"],
        cwd=eof_project,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdin
    assert process.stdout
    assert process.stderr

    def rpc(request_id: int, method: str, params: dict) -> dict:
        assert process.stdin
        assert process.stdout
        process.stdin.write(
            json.dumps(
                {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
            )
            + "\n"
        )
        process.stdin.flush()
        assert select.select([process.stdout], [], [], 10)[0], "No MCP response"
        return json.loads(process.stdout.readline())

    try:
        initialized = rpc(
            1,
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        )
        assert initialized["id"] == 1
        process.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        )
        process.stdin.flush()
        response = rpc(2, "tools/call", {"name": "eof_tool", "arguments": {}})
        assert response["id"] == 2
        assert not response["result"].get("isError")
        assert not marker.exists()
        assert not payloads
        started = time.monotonic()
        process.stdin.close()
        process.wait(timeout=3)
        assert time.monotonic() - started < 2.2
        assert process.returncode == 0
        assert process.stdout.read() == ""
        stderr = process.stderr.read()
        assert f"127.0.0.1:{port}" not in stderr
        if mode == "off":
            assert not marker.exists()
            assert not payloads
        else:
            assert marker.read_text() == "called\n"
            if mode in {"unavailable", "hanging"}:
                assert "telemetry_export_failed" in stderr
            if mode == "hanging":
                assert payloads
            if mode == "success":
                assert {path for path, _ in payloads} == {
                    "/base/v1/traces",
                    "/base/v1/metrics",
                }
                payload = json.dumps(payloads)
                assert '"tool.call"' in payload
                assert '"eof_tool"' in payload
                assert '"tool.calls"' in payload
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=3)
        if mode != "unavailable":
            collector.shutdown()
            collector.server_close()
