"""Exercise composed forms over generated MCP transports and an HTTP upstream."""

import asyncio
import json
import os
import subprocess
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from openapi_to_mcp.adapters.testing import (
    ConnectionSettings,
    ServerTestRequest,
    execute_mcp_server,
)
from openapi_to_mcp.cli import cli
from openapi_to_mcp.common.form_media import normalize_form_media
from tests.integration.http_health_support import running_server
from tests.integration.test_form_media_wire import Capture
from tests.integration.test_query_serialization import _build


@pytest.mark.parametrize("transport", ["stdio", "streamable-http"])
@pytest.mark.parametrize("validation", ["input", "none"])
def test_composed_wire(tmp_path: Path, transport: str, validation: str) -> None:
    source = Path(__file__).parents[1] / "resources/form_compatibility/composed.yaml"
    spec = yaml.safe_load(source.read_text())
    del spec["paths"]["/neighbor"]
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec))
    out = tmp_path / "generated"
    result = CliRunner().invoke(
        cli,
        [
            "generate",
            "-o",
            str(path),
            "-d",
            str(out),
            "--transport",
            transport,
            "--runtime-validation",
            validation,
        ],
    )
    assert result.exit_code == 0, result.output
    _build(out)
    # Call the generated serializer directly so MCP SDK validation cannot mask
    # its own structural checks.
    media = spec["paths"]["/send"]["post"]["requestBody"]["content"][
        "application/x-www-form-urlencoded"
    ]
    metadata = normalize_form_media(spec, media)
    script = tmp_path / "shape.mjs"
    script.write_text(
        "import {serializeForm} from "
        + json.dumps((out / "build/runtime/form_media.js").as_uri())
        + ";\n"
        + "const m = "
        + json.dumps(metadata)
        + ";\n"
        + "for (const v of [{name:'x',count:'2'}, {name:'x',count:2,unknown:1}]) {"
        + "let failed=false; try { serializeForm(v,m); } catch { failed=true; }"
        + "if (!failed) throw new Error('invalid shape accepted'); }\n"
        + "if (serializeForm({name:'x',count:10},m).wire !== 'name=x&count=10') throw new Error('range rejected');\n"
    )
    subprocess.run(  # noqa: S603
        ["node", str(script)],  # noqa: S607
        check=True,
        env={**os.environ, "TARGET_API_BASE_URL": "http://127.0.0.1"},
    )
    Capture.requests = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), Capture)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"

    async def exercise(connection: ConnectionSettings) -> None:
        async def call(value: dict) -> dict:
            response = await execute_mcp_server(
                ServerTestRequest(
                    transport,
                    "call",
                    {
                        "tool_name": "sendComposed",
                        "tool_arguments": {"whole": value, "requestBody": value},
                    },
                    connection=connection,
                )
            )
            return response.get("result", response)

        good = await call({"name": "a + b", "count": 2})
        assert not good.get("isError", False), good
        for value in (
            {"name": "a + b", "count": "wrong"},
            {"name": "a + b", "count": 2, "unknown": "x"},
        ):
            failure = await call(value)
            assert failure.get("isError") is True, failure
        if validation == "input":
            for value in (
                {"count": 2},
                {"name": "a", "count": 2},
                {"name": "valid", "count": 10},
            ):
                failure = await call(value)
                assert failure.get("isError") is True, failure
        else:
            result = await call({"name": "a", "count": 10})
            assert not result.get("isError", False), result

    try:
        env = {"TARGET_API_BASE_URL": base}
        if transport == "stdio":
            asyncio.run(
                exercise(
                    ConnectionSettings(
                        server_cmd=f"node {out / 'build/index.js'}", env=env
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
    assert Capture.requests == [
        (
            "/send?name=a+%2B+b&count=2",
            "name=a%20%2B%20b&count=2",
            "application/x-www-form-urlencoded",
        ),
        *(
            [
                (
                    "/send?name=a&count=10",
                    "name=a&count=10",
                    "application/x-www-form-urlencoded",
                )
            ]
            if validation == "none"
            else []
        ),
    ]
