#!/usr/bin/env python3
"""Small local HTTP target used for generated-server E2E validation."""

from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import ParseResult, parse_qs, urlparse

AUTH_CREDENTIALS = {
    "/auth/header": ("header", "X-API-Key", "header-secret"),
    "/auth/query": ("query", "api_key", "query-secret"),
    "/auth/cookie": ("cookie", "session_token", "cookie-secret"),
    "/auth/bearer": ("bearer", "Authorization", "bearer-secret"),
}


class MockTargetApiHandler(BaseHTTPRequestHandler):
    """Serve deterministic responses for generated MCP server tests."""

    server_version = "openapi-to-mcp-mock/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/health":
            self._send_json(HTTPStatus.OK, {"ok": True})
            return

        if parsed.path == "/test":
            query = self._query_params(parsed.query)
            if query.get("status") == "server_error":
                self._send_json(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {"ok": False, "error": "temporary upstream issue"},
                )
                return
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

        if parsed.path in AUTH_CREDENTIALS:
            self._handle_auth_request(parsed)
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

    def _query_params(self, query_string: str) -> dict[str, object]:
        return {
            key: values[0] if len(values) == 1 else values
            for key, values in parse_qs(query_string, keep_blank_values=True).items()
        }

    def _cookie_params(self) -> dict[str, str]:
        parsed = SimpleCookie(self.headers.get("Cookie", ""))
        return {key: morsel.value for key, morsel in parsed.items()}

    def _received_credential(
        self, auth_kind: str, auth_name: str, parsed_query: dict[str, object]
    ) -> str | None:
        if auth_kind == "query":
            value = parsed_query.get(auth_name)
            return value if isinstance(value, str) else None
        if auth_kind == "cookie":
            return self._cookie_params().get(auth_name)
        return self.headers.get(auth_name)

    def _handle_auth_request(self, parsed: ParseResult) -> None:
        path = parsed.path
        query_string = parsed.query
        auth_kind, auth_name, expected = AUTH_CREDENTIALS[path]
        parsed_query = self._query_params(query_string)
        received = self._received_credential(auth_kind, auth_name, parsed_query)
        valid = received == expected
        if auth_kind == "bearer":
            valid = received == f"Bearer {expected}"

        if not valid:
            self._send_json(
                HTTPStatus.UNAUTHORIZED,
                {
                    "ok": False,
                    "auth": auth_kind,
                    "error": "Missing or invalid credential",
                    "received": received,
                },
            )
            return

        self._send_json(
            HTTPStatus.OK,
            {"ok": True, "auth": auth_kind, "credential": expected},
        )


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
