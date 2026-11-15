"""Exercise exported telemetry against a loopback collector."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner


def test_runtime_telemetry_exports_bounded_data(  # noqa: C901, PLR0915
    runner: CliRunner, tmp_path: Path
) -> None:
    """Tool calls, retries, cache, and size limits export without request content."""
    output = tmp_path / "server"
    result = runner.invoke(
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
    assert result.exit_code == 0, result.output
    (output / "src/custom/tools.ts").write_text("""
import type { CustomToolDefinition } from '../runtime/generated.js';
export function getCustomTools(): CustomToolDefinition[] {
  return [{ tool: { name: 'custom_known', description: 'test', inputSchema: { type: 'object', properties: {} } }, handler: async () => ({ content: [{ type: 'text', text: 'CUSTOM_BODY_MARKER' }] }) }];
}
""")
    npm = shutil.which("npm")
    node = shutil.which("node")
    assert npm
    assert node
    for command in (
        [npm, "install", "--ignore-scripts", "--no-audit", "--no-fund"],
        [npm, "run", "build"],
    ):
        subprocess.run(command, cwd=output, check=True, capture_output=True, text=True)  # noqa: S603

    received: list[tuple[str, dict, dict]] = []
    attempts: dict[str, int] = {}

    class Collector(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            if self.headers.get("Transfer-Encoding", "").lower() == "chunked":
                chunks = []
                while True:
                    size = int(self.rfile.readline().strip().split(b";")[0], 16)
                    if not size:
                        self.rfile.readline()
                        break
                    chunks.append(self.rfile.read(size))
                    self.rfile.read(2)
                body = b"".join(chunks)
            else:
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            received.append((self.path, dict(self.headers), json.loads(body)))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def do_GET(self) -> None:
            attempts[self.path] = attempts.get(self.path, 0) + 1
            status = 503 if "retry" in self.path and attempts[self.path] == 1 else 200
            body = b"x" * 1000 if "large" in self.path else b'{"value":"BODY_MARKER"}'
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Collector)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}"
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("MCP_", "OTEL_", "AUTH_", "TARGET_API_"))
    }
    env.update(
        {
            "MCP_OTEL_ENABLED": "on",
            "MCP_OTEL_EXPORTER_OTLP_ENDPOINT": endpoint + "/base",
            "MCP_OTEL_METRICS_INTERVAL_MS": "1000",
            "MCP_OTEL_SERVICE_NAME": "test-service",
            "TARGET_API_BASE_URL": endpoint,
            "AUTH_DEMO_API_KEY": "KEY_MARKER",
            "MCP_CACHE_TTL_MS": "60000",
            "MCP_RETRY_MAX_RETRIES": "1",
            "MCP_RETRY_BUDGET_PER_MINUTE": "10",
            "MCP_MAX_RESPONSE_BYTES": "100",
            "OTEL_EXPORTER_OTLP_HEADERS": "authorization=HEADER_MARKER",
            "OTEL_RESOURCE_ATTRIBUTES": "secret=RESOURCE_MARKER",
            "OTEL_SERVICE_NAME": "SERVICE_MARKER",
            "OTEL_LOG_LEVEL": "ALL",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://127.0.0.1:1",
        }
    )
    process = subprocess.Popen(  # noqa: S603
        [node, "build/index.js"],
        cwd=output,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdin
    assert process.stdout
    assert process.stderr

    def call(request_id: int, method: str, params: dict) -> dict:
        assert process.stdin
        assert process.stdout
        process.stdin.write(
            json.dumps(
                {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
            )
            + "\n"
        )
        process.stdin.flush()
        return json.loads(process.stdout.readline())

    try:
        call(
            1,
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "CALLER_MARKER", "version": "1"},
            },
        )
        process.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        )
        process.stdin.flush()
        for request_id, arg in enumerate(
            ("ARG_MARKER-retry", "ARG_MARKER-retry", "ARG_MARKER-large"), 2
        ):
            result = call(
                request_id,
                "tools/call",
                {"name": "getWidget", "arguments": {"widgetId": arg}},
            )["result"]
            assert bool(result.get("isError")) == (request_id == 4)
        call(
            5,
            "tools/call",
            {"name": "custom_known", "arguments": {"private": "CUSTOM_ARG_MARKER"}},
        )
        assert "error" in call(
            6, "tools/call", {"name": "UNKNOWN_NAME_MARKER", "arguments": {}}
        )
        time.sleep(2)
        start = time.monotonic()
        process.send_signal(signal.SIGTERM)
        process.wait(timeout=3)
        assert time.monotonic() - start < 2.2
        assert process.returncode == 0
        stderr = process.stderr.read()
        assert "telemetry_export_failed" not in stderr
        payload = json.dumps(received)
        assert {path for path, _, _ in received} == {
            "/base/v1/traces",
            "/base/v1/metrics",
        }
        for marker in (
            "BODY_MARKER",
            "ARG_MARKER",
            "KEY_MARKER",
            "HEADER_MARKER",
            "RESOURCE_MARKER",
            "SERVICE_MARKER",
            "CALLER_MARKER",
            "CUSTOM_BODY_MARKER",
            "CUSTOM_ARG_MARKER",
            "UNKNOWN_NAME_MARKER",
        ):
            assert marker not in payload
        for name in (
            "tool.calls",
            "tool.duration",
            "cache.hit",
            "retry",
            "response_budget.rejection",
            "tool.call",
            "upstream.attempt",
            "response_too_large",
        ):
            assert name in payload
        spans = [
            span
            for path, _, data in received
            if path.endswith("traces")
            for resource in data.get("resourceSpans", [])
            for scope in resource.get("scopeSpans", [])
            for span in scope.get("spans", [])
        ]
        roots = [span for span in spans if span["name"] == "tool.call"]
        assert len(roots) == 4
        assert (
            sum(
                any(
                    attr.get("key") == "tool.name"
                    and attr.get("value", {}).get("stringValue") == "custom_known"
                    for attr in span.get("attributes", [])
                )
                for span in roots
            )
            == 1
        )
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=3)
        server.shutdown()
        server.server_close()


def test_http_telemetry_shutdown_before_first_session(
    runner: CliRunner, tmp_path: Path
) -> None:
    """A ready listener shuts down its process-wide SDK even without sessions."""
    from tests.integration.http_health_support import running_server  # noqa: PLC0415

    output = tmp_path / "http-server"
    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            "examples/container/openapi.yaml",
            "--output-dir",
            str(output),
            "--transport",
            "streamable-http",
            "--telemetry",
            "opentelemetry",
        ],
    )
    assert result.exit_code == 0, result.output
    npm = shutil.which("npm")
    assert npm
    for command in (
        [npm, "install", "--ignore-scripts", "--no-audit", "--no-fund"],
        [npm, "run", "build"],
    ):
        subprocess.run(command, cwd=output, check=True, capture_output=True, text=True)  # noqa: S603

    marker = output / "shutdown-observed"
    probe = output / "shutdown-probe.mjs"
    probe.write_text("""
import { NodeSDK } from '@opentelemetry/sdk-node';
import { writeFileSync } from 'node:fs';
const original = NodeSDK.prototype.shutdown;
NodeSDK.prototype.shutdown = function (...args) {
  writeFileSync(process.env.TEST_SHUTDOWN_MARKER, 'called');
  return original.apply(this, args);
};
""")
    with running_server(
        output,
        MCP_OTEL_ENABLED="on",
        MCP_OTEL_EXPORTER_OTLP_ENDPOINT="http://127.0.0.1:9/collector",
        NODE_OPTIONS=f"--import={probe}",
        TEST_SHUTDOWN_MARKER=str(marker),
    ) as (_base, process):
        assert not marker.exists()
        started = time.monotonic()
        process.send_signal(signal.SIGTERM)
        process.wait(timeout=3)
        assert time.monotonic() - started < 2.2
        assert process.returncode == 0
        assert marker.read_text() == "called"
        assert process.stdout
        assert process.stdout.read() == ""
