"""Generated JSON whole queries accept boolean references with normal validation."""

from __future__ import annotations

import asyncio
import json
import threading
from http.server import ThreadingHTTPServer
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from openapi_to_mcp.adapters.testing import (
    ConnectionSettings,
    ServerTestRequest,
    execute_mcp_server,
)
from openapi_to_mcp.cli import cli
from tests.integration.http_health_support import running_server
from tests.integration.test_form_media_wire import Capture
from tests.integration.test_query_serialization import _build

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("transport", ["stdio", "streamable-http"])
def test_boolean_whole_json_query_wire(tmp_path: Path, transport: str) -> None:
    spec = {
        "openapi": "3.2.1",
        "info": {"title": "Boolean JSON query", "version": "1"},
        "components": {
            "schemas": {
                "Any": True,
                "Never": False,
                "AnyAlias": {"$ref": "#/components/schemas/Any"},
                "NeverAlias": {"$ref": "#/components/schemas/Never"},
            }
        },
        "paths": {},
    }
    spec["x-schemas"] = {"String/Value": {"type": "string", "minLength": 3}}
    cases = []
    for label, boolean in (("Any", True), ("Never", False)):
        spec["x-schemas"].update(
            {
                f"{label}/Value": boolean,
                f"{label}~Value": boolean,
                f"{label}~1Value": boolean,
                f"{label}/Alias": {"$ref": f"#/x-schemas/{label}~1Value"},
                f"{label}~Alias": {"$ref": f"#/x-schemas/{label}%7E0Value"},
            }
        )
        for suffix, schema in (
            ("Inline", boolean),
            ("Ref", {"$ref": f"#/components/schemas/{label}"}),
            ("Chain", {"$ref": f"#/components/schemas/{label}Alias"}),
            ("Slash", {"$ref": f"#/x-schemas/{label}~1Value"}),
            ("Tilde", {"$ref": f"#/x-schemas/{label}~0Value"}),
            ("SlashChain", {"$ref": f"#/x-schemas/{label}~1Alias"}),
            ("TildeChain", {"$ref": f"#/x-schemas/{label}~0Alias"}),
            ("EncodedSlash", {"$ref": f"#/x-schemas%2F{label}%7E1Value"}),
            ("EncodedTilde", {"$ref": f"#/x-schemas/{label}%7E0Value"}),
            ("Once", {"$ref": f"#/x-schemas/{label}~01Value"}),
        ):
            cases.append((label.lower() + suffix, schema))
    cases.append(("dictionary", {"$ref": "#/x-schemas/String~1Value"}))
    for name, schema in cases:
        spec["paths"][f"/{name}"] = {
            "get": {
                "operationId": name,
                "parameters": [
                    {
                        "name": "whole",
                        "in": "querystring",
                        "required": True,
                        "content": {"application/json": {"schema": schema}},
                    }
                ],
                "responses": {"200": {"description": "OK"}},
            }
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

    async def exercise(connection: ConnectionSettings) -> None:
        listed = await execute_mcp_server(
            ServerTestRequest(transport, "list", connection=connection)
        )
        listed = listed.get("result", listed)
        tools = {tool["name"]: tool for tool in listed["tools"]}
        for name, tool in tools.items():
            field = tool["inputSchema"]["properties"]["whole"]
            assert ("not" in field) == name.startswith("never")
            assert tool["inputSchema"]["required"] == ["whole"]
        for name in tools:
            values = (
                ("a + b", "x")
                if name == "dictionary"
                else ({"label": "é +%&="}, [1, "a b"], False)
                if name
                in {
                    "anyInline",
                    "anyRef",
                    "anyChain",
                    "neverInline",
                    "neverRef",
                    "neverChain",
                }
                else ({"label": "é +%&="},)
            )
            for value in values:
                response = await execute_mcp_server(
                    ServerTestRequest(
                        transport,
                        "call",
                        {"tool_name": name, "tool_arguments": {"whole": value}},
                        connection=connection,
                    )
                )
                response = response.get("result", response)
                assert bool(response.get("isError")) == (
                    name.startswith("never") or (name == "dictionary" and value == "x")
                ), response

    try:
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
    expected_queries = (
        "%7B%22label%22%3A%22%C3%A9%20%2B%25%26%3D%22%7D",
        "%5B1%2C%22a%20b%22%5D",
        "false",
    )
    assert [path for path, _, _ in Capture.requests] == [
        *(
            f"/{name}?{query}"
            for name, _ in cases
            if name.startswith("any")
            for query in (
                expected_queries
                if name in {"anyInline", "anyRef", "anyChain"}
                else expected_queries[:1]
            )
        ),
        "/dictionary?%22a%20%2B%20b%22",
    ]
    assert all(not body for _, body, _ in Capture.requests)
