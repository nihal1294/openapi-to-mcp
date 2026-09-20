from __future__ import annotations

import asyncio
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, Any, ClassVar

from click.testing import CliRunner

from openapi_to_mcp.adapters.testing import (
    ConnectionSettings,
    ServerTestRequest,
    execute_mcp_server,
)
from openapi_to_mcp.cli import cli
from tests.integration.query_serialization_spec import write_query_spec

if TYPE_CHECKING:
    from pathlib import Path


class _QueryCaptureHandler(BaseHTTPRequestHandler):
    paths: ClassVar[list[str]] = []

    def do_GET(self) -> None:
        self.__class__.paths.append(self.path)
        body = b'{"ok":true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def test_generated_runtime_serializes_query_values_per_parameter(
    tmp_path: Path,
) -> None:
    _QueryCaptureHandler.paths = []
    spec_path = write_query_spec(tmp_path / "query.json")
    output_dir = tmp_path / "generated"
    result = CliRunner().invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            str(spec_path),
            "--output-dir",
            str(output_dir),
            "--transport",
            "stdio",
        ],
    )
    assert result.exit_code == 0, result.output
    _build(output_dir)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _QueryCaptureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        response = asyncio.run(_call_generated_server(output_dir, server.server_port))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert response["isError"] is False
    assert len(_QueryCaptureHandler.paths) == 1
    request_target = _QueryCaptureHandler.paths[0]
    assert "preserved=a/b?c" in request_target
    assert "encoded=a%2Fb%3Fc" in request_target
    assert "percent=already%2Fencoded" in request_target
    assert "space=hello+world" in request_target
    assert "danger=x%23y%26z%3Dq%2B%5Bbrackets%5D" in request_target
    assert "&z=q" not in request_target
    assert "tags[]=first%2Fvalue&tags[]=two%26three" in request_target
    assert "filter=value/with?query" in request_target
    assert "deep[name]=a%2Fb" in request_target
    assert request_target.count("q=final") == 1
    assert "q=from-object" not in request_target
    assert "foo[]=literal&foo=plain" in request_target
    assert "auth[]=visible" in request_target
    assert "auth=token%2Fwith%26delimiters%3Dhere%23" in request_target


def _build(output_dir: Path) -> None:
    npm = shutil.which("npm")
    if npm is None:
        raise RuntimeError("npm is required for generated runtime integration tests")
    subprocess.run(  # noqa: S603
        [npm, "install", "--ignore-scripts"], cwd=output_dir, check=True
    )
    subprocess.run([npm, "run", "build"], cwd=output_dir, check=True)  # noqa: S603


async def _call_generated_server(output_dir: Path, port: int) -> dict[str, Any]:
    connection = ConnectionSettings(
        server_cmd=f"node {output_dir / 'build' / 'index.js'}",
        env={
            "TARGET_API_BASE_URL": f"http://127.0.0.1:{port}",
            "AUTH_QUERYAUTH_API_KEY": "token/with&delimiters=here#",
        },
    )
    return await execute_mcp_server(
        ServerTestRequest(
            "stdio",
            "call",
            {
                "tool_name": "search",
                "tool_arguments": {
                    "preserved": "a/b?c",
                    "encoded": "a/b?c",
                    "percent": "already%2Fencoded",
                    "space": "hello world",
                    "danger": "x#y&z=q+[brackets]",
                    "tags": ["first/value", "two&three"],
                    "filters": {"filter": "value/with?query"},
                    "deep": {"name": "a/b"},
                    "qObject": {"q": "from-object"},
                    "q": "final",
                    "foo[]": "literal",
                    "foo": "plain",
                    "auth[]": "visible",
                },
            },
            connection=connection,
        )
    )
