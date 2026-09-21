"""Operational probes on a compiled, running generated HTTP server."""

from __future__ import annotations

import asyncio
import json
import shutil
import signal
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

import pytest
import requests

from openapi_to_mcp.adapters.testing import (
    ConnectionSettings,
    ServerTestRequest,
    execute_mcp_server,
)
from tests.integration.http_health_support import (
    build_http_server,
    launch_server,
    running_server,
    stop_server,
)


@pytest.fixture(scope="module")
def generated_http(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_http_server(tmp_path_factory.mktemp("generated-http-health"))


def test_readiness_transitions_over_http(generated_http: Path) -> None:
    node = shutil.which("node")
    assert node is not None
    script = Path(__file__).parents[1] / "resources/http_health_lifecycle.mjs"
    result = subprocess.run(  # noqa: S603
        [node, str(script), str(generated_http)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("endpoint", ["/mcp", "/custom/mcp", "/"])
def test_probes_work_without_mcp_session_or_upstream_credentials(
    generated_http: Path, endpoint: str
) -> None:
    with running_server(generated_http, MCP_HTTP_ENDPOINT=endpoint) as (base, _):
        for path, status in (("/healthz", "ok"), ("/readyz", "ready")):
            response = requests.get(base + path, timeout=2)
            assert response.status_code == 200
            assert response.json() == {"status": status}
            assert response.headers["Cache-Control"] == "no-store"
            assert "Mcp-Session-Id" not in response.headers
            head = requests.head(base + path, timeout=2)
            assert head.status_code == 200
            assert head.content == b""
            assert head.headers["Cache-Control"] == "no-store"
            assert requests.post(base + path, json={}, timeout=2).status_code == 405
            malformed = requests.post(
                base + path,
                data="{",
                headers={"Content-Type": "application/json"},
                timeout=2,
            )
            assert malformed.status_code == 405
        assert requests.get(base + endpoint, timeout=2).status_code == 400


@pytest.mark.parametrize("path", ["/healthz", "/readyz"])
@pytest.mark.parametrize(
    "headers", [{"Host": "untrusted.invalid"}, {"Origin": "https://untrusted.invalid"}]
)
def test_probes_enforce_http_allowlists(
    generated_http: Path, path: str, headers: dict[str, str]
) -> None:
    with running_server(generated_http) as (base, _):
        response = requests.get(base + path, headers=headers, timeout=2)
        assert response.status_code == 403


@pytest.mark.parametrize(
    "endpoint",
    [
        "/healthz",
        "/HEALTHZ/",
        "/readyz/",
        "/:name",
        "/{*path}",
        "/healthz/{*rest}",
        "/readyz/{*rest}",
    ],
)
def test_reserved_probe_routes_cannot_be_mcp_endpoints(
    generated_http: Path, endpoint: str
) -> None:
    process, _ = launch_server(generated_http, MCP_HTTP_ENDPOINT=endpoint)
    try:
        stdout, stderr = process.communicate(timeout=5)
        assert process.returncode != 0
        assert "MCP_HTTP_ENDPOINT" in stderr
        assert "healthz" in stderr or "readyz" in stderr
        assert "listening on" not in stdout + stderr
    finally:
        stop_server(process)


def test_invalid_startup_does_not_advertise_readiness(generated_http: Path) -> None:
    process, _ = launch_server(generated_http, TARGET_API_BASE_URL="ws://localhost")
    try:
        _, stderr = process.communicate(timeout=5)
        assert process.returncode != 0
        assert "TARGET_API_BASE_URL" in stderr
        assert "listening on" not in stderr
    finally:
        stop_server(process)


@pytest.mark.parametrize("initialize", [False, True])
def test_sigterm_stops_probes_before_and_after_mcp_session(
    generated_http: Path, *, initialize: bool
) -> None:
    with running_server(generated_http) as (base, process):
        assert requests.get(base + "/readyz", timeout=2).status_code == 200
        if initialize:
            listed = asyncio.run(
                execute_mcp_server(
                    ServerTestRequest(
                        "streamable-http",
                        "list",
                        connection=ConnectionSettings(endpoint_url=base + "/mcp"),
                    )
                )
            )
            assert "result" in listed
            assert "tools" in listed["result"]
        process.terminate()
        process.wait(timeout=5)
        assert process.returncode in (0, -signal.SIGTERM)
        with pytest.raises(requests.ConnectionError):
            requests.get(base + "/readyz", timeout=1)


class _WidgetHandler(BaseHTTPRequestHandler):
    calls: ClassVar[list[tuple[str, str | None]]] = []

    def do_GET(self) -> None:
        self.calls.append((self.path, self.headers.get("X-API-Key")))
        assert self.path == "/widgets/42"
        assert self.headers.get("X-API-Key") == "health-test-key"
        body = b'{"id":"42","source":"health-test"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def test_operational_probes_preserve_authenticated_mcp_calls(
    generated_http: Path,
) -> None:
    _WidgetHandler.calls = []
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _WidgetHandler)
    thread = threading.Thread(target=upstream.serve_forever, daemon=True)
    thread.start()
    try:
        with running_server(
            generated_http,
            MCP_HTTP_ENDPOINT="/custom/mcp",
            TARGET_API_BASE_URL=f"http://127.0.0.1:{upstream.server_port}",
            AUTH_DEMO_API_KEY="health-test-key",
        ) as (base, _):
            assert requests.get(base + "/readyz", timeout=2).status_code == 200
            assert _WidgetHandler.calls == []
            response = asyncio.run(
                execute_mcp_server(
                    ServerTestRequest(
                        "streamable-http",
                        "call",
                        {
                            "tool_name": "getWidget",
                            "tool_arguments": {"widgetId": "42"},
                        },
                        connection=ConnectionSettings(
                            endpoint_url=base + "/custom/mcp"
                        ),
                    )
                )
            )
            payload = response.get("result", response)
            assert not payload.get("isError")
            assert json.loads(payload["content"][0]["text"]) == {
                "id": "42",
                "source": "health-test",
            }
            assert _WidgetHandler.calls == [("/widgets/42", "health-test-key")]
    finally:
        upstream.shutdown()
        upstream.server_close()
        thread.join(timeout=5)
