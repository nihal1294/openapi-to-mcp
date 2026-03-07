#!/usr/bin/env python3
"""Small local HTTP target used for generated-server E2E validation."""

from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


class MockTargetApiHandler(BaseHTTPRequestHandler):
    """Serve deterministic responses for generated MCP server tests."""

    server_version = "openapi-to-mcp-mock/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/health":
            self._send_json(HTTPStatus.OK, {"ok": True})
            return

        if parsed.path == "/test":
            query = {
                key: values[0] if len(values) == 1 else values
                for key, values in parse_qs(
                    parsed.query, keep_blank_values=True
                ).items()
            }
            self._send_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "path": parsed.path,
                    "query": query,
                    "status": query.get("status", "available"),
                },
            )
            return

        self._send_json(
            HTTPStatus.NOT_FOUND,
            {"ok": False, "error": f"Unhandled path: {parsed.path}"},
        )

    def log_message(self, log_format: str, *args: object) -> None:
        """Keep default logging concise but still available in CI logs."""
        print(log_format % args)  # noqa: T201

    def _send_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18080)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), MockTargetApiHandler)
    print(f"Mock target API listening on http://{args.host}:{args.port}")  # noqa: T201
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
