"""Compare bounded public contracts between two repository revisions.

The runner deliberately uses fixed OpenAPI fixtures whose digests are checked
before either revision is generated.  It reports only the exercised contracts:
Click metadata, runtime floors, generated tool schemas, auth placeholders, and
a compiled/running custom-tool consumer.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import tomllib
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

FIXTURE_DIGESTS = {
    "basic.yaml": "2fe11c7a45b57ffd24ad03e3dac0c6bc7c9d8b8036da108fbbf445741692cb0e",
    "auth.yaml": "c26ddc7cf0f848f80cce101e812b84ff1d412f4edba0cc69bdbceab0552bddce",
}
IMPACT_ORDER = {"none": 0, "patch": 1, "minor": 2, "breaking": 3}


def _impact(reasons: list[str]) -> str:
    breaking_prefixes = (
        "cli-command-removed",
        "cli-option-removed",
        "cli-option-now-required",
        "cli-option-default-changed",
        "cli-option-type-changed",
        "generated-tool-removed",
        "auth-contract-removed",
        "schema-changed",
        "python-runtime-floor-raised",
        "node-runtime-floor-raised",
    )
    if any(reason.startswith(breaking_prefixes) for reason in reasons):
        return "breaking"
    if any(
        reason.startswith(
            ("generated-tool-added", "cli-command-added", "cli-option-added")
        )
        for reason in reasons
    ):
        return "minor"
    return "none"


def compare_contracts(  # noqa: C901, PLR0912
    base: dict[str, object], head: dict[str, object]
) -> dict[str, object]:
    """Return the minimum semantic impact for two already-collected contracts."""
    reasons: list[str] = []
    complete = True
    for label, contract in (("base", base), ("head", head)):
        runtime = contract.get("generated", {}).get("runtime", {})  # type: ignore[union-attr]
        for check in (
            "stdio_compiled",
            "stdio_list",
            "stdio_call",
            "stdio_custom",
            "http_compiled",
            "http_list",
            "http_call",
            "http_custom",
        ):
            if runtime.get(check) is not True:
                reasons.append(f"runtime-evidence-incomplete:{label}:{check}")
                complete = False

    base_cli = base["cli"]  # type: ignore[index]
    head_cli = head["cli"]  # type: ignore[index]
    for command, base_command in base_cli.items():  # type: ignore[union-attr]
        if command not in head_cli:
            reasons.append(f"cli-command-removed:{command}")
            continue
        base_options = base_command["options"]
        head_options = head_cli[command]["options"]
        for option, base_metadata in base_options.items():
            if option not in head_options:
                reasons.append(f"cli-option-removed:{command}:{option}")
                continue
            head_metadata = head_options[option]
            if not base_metadata.get("required") and head_metadata.get("required"):
                reasons.append(f"cli-option-now-required:{command}:{option}")
            if base_metadata.get("default") != head_metadata.get("default"):
                reasons.append(f"cli-option-default-changed:{command}:{option}")
            if base_metadata.get("type") != head_metadata.get("type"):
                reasons.append(f"cli-option-type-changed:{command}:{option}")
    for command, head_command in head_cli.items():
        if command not in base_cli:
            reasons.append(f"cli-command-added:{command}")
            continue
        reasons.extend(
            f"cli-option-added:{command}:{option}"
            for option in head_command["options"]
            if option not in base_cli[command]["options"]
        )

    for floor in ("python_floor", "node_floor"):
        before = str(base[floor])
        after = str(head[floor])
        if _floor_tuple(after) > _floor_tuple(before):
            reasons.append(
                f"{floor.replace('_floor', '')}-runtime-floor-raised:{before}->{after}"
            )

    base_generated = base["generated"]  # type: ignore[index]
    head_generated = head["generated"]  # type: ignore[index]
    base_tools = base_generated["tools"]
    head_tools = head_generated["tools"]
    for name, schema in base_tools.items():
        if name not in head_tools:
            reasons.append(f"generated-tool-removed:{name}")
        elif schema != head_tools[name]:
            reasons.append(f"schema-changed:{name}")
    reasons.extend(
        f"generated-tool-added:{name}" for name in head_tools if name not in base_tools
    )
    reasons.extend(
        f"auth-contract-removed:{name}"
        for name in base_generated["auth_env"]
        if name not in head_generated["auth_env"]
    )

    minimum = "needs-review" if not complete else _impact(reasons)
    return {"minimum": minimum, "reasons": sorted(reasons), "complete": complete}


def _floor_tuple(value: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", value)
    return tuple(int(number) for number in numbers) if numbers else (0,)


def _run(
    command: list[str], *, cwd: Path, timeout: int = 180
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        command, cwd=cwd, text=True, capture_output=True, check=True, timeout=timeout
    )


def _read_fixture(path: Path) -> Path:
    expected = FIXTURE_DIGESTS[path.name]
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(f"fixture digest changed: {path.name}")
    return path


def _write_custom_tool(path: Path) -> None:
    path.write_text(
        """import type { CustomToolDefinition } from '../runtime/generated.js';

export function getCustomTools(): CustomToolDefinition[] {
  return [{
    tool: { name: 'contractCustomTool', description: 'Release contract fixture.', inputSchema: { type: 'object', properties: { message: { type: 'string' } }, required: ['message'] } },
    handler: async (args) => ({ content: [{ type: 'text', text: `custom:${String(args.message)}` }] }),
  }];
}
""",
        encoding="utf-8",
    )


class _TargetHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = json.dumps({"ok": True, "status": "available"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def _run_stdio_contract(project: Path) -> dict[str, bool]:
    from openapi_to_mcp.adapters.testing import (  # noqa: PLC0415
        ConnectionSettings,
        ServerTestRequest,
        execute_mcp_server,
    )

    server = ThreadingHTTPServer(("127.0.0.1", 0), _TargetHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    connection = ConnectionSettings(
        server_cmd=f"node {project / 'build' / 'index.js'}",
        env={"TARGET_API_BASE_URL": base_url},
    )
    try:
        listed = asyncio.run(
            execute_mcp_server(
                ServerTestRequest("stdio", "list", connection=connection)
            )
        )
        names = [tool["name"] for tool in listed.get("tools", [])]
        generated = asyncio.run(
            execute_mcp_server(
                ServerTestRequest(
                    "stdio",
                    "call",
                    {
                        "tool_name": "testConversionTool",
                        "tool_arguments": {"status": "available"},
                    },
                    2,
                    connection,
                )
            )
        )
        custom = asyncio.run(
            execute_mcp_server(
                ServerTestRequest(
                    "stdio",
                    "call",
                    {
                        "tool_name": "contractCustomTool",
                        "tool_arguments": {"message": "ok"},
                    },
                    3,
                    connection,
                )
            )
        )
        return {
            "compiled": True,
            "list": "testConversionTool" in names and "contractCustomTool" in names,
            "call": generated.get("isError") is not True and "error" not in generated,
            "custom": "custom:ok" in json.dumps(custom),
        }
    finally:
        server.shutdown()
        server.server_close()


def _request_http(
    endpoint: str, payload: dict[str, object], headers: dict[str, str]
) -> tuple[dict[str, object], dict[str, str]]:
    request = urllib.request.Request(  # noqa: S310
        endpoint,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
        return json.loads(response.read()), dict(response.headers.items())


def _reserve_port() -> int:
    port_socket = __import__("socket").socket()
    port_socket.bind(("127.0.0.1", 0))
    port = port_socket.getsockname()[1]
    port_socket.close()
    return port


def _run_http_contract(project: Path, port: int) -> dict[str, bool]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _TargetHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("node is required for release contract evidence")
    process = subprocess.Popen(  # noqa: S603
        [node, str(project / "build" / "index.js")],
        cwd=project,
        env={
            **os.environ,
            "PORT": str(port),
            "TARGET_API_BASE_URL": f"http://127.0.0.1:{server.server_port}",
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    endpoint = f"http://127.0.0.1:{port}/mcp"
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": "2025-11-25",
    }
    try:
        for _ in range(30):
            try:
                _initialized, response_headers = _request_http(
                    endpoint,
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2025-11-25",
                            "capabilities": {},
                            "clientInfo": {"name": "release-contract", "version": "1"},
                        },
                    },
                    headers,
                )
                break
            except OSError:
                time.sleep(0.2)
        else:
            raise RuntimeError("generated streamable HTTP server did not start")
        session_id = next(
            (
                value
                for name, value in response_headers.items()
                if name.lower() == "mcp-session-id"
            ),
            "",
        )
        if not session_id:
            raise RuntimeError("generated streamable HTTP server omitted a session id")
        headers["Mcp-Session-Id"] = session_id
        listed, _ = _request_http(
            endpoint,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            headers,
        )
        generated, _ = _request_http(
            endpoint,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "testConversionTool",
                    "arguments": {"status": "available"},
                },
            },
            headers,
        )
        custom, _ = _request_http(
            endpoint,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "contractCustomTool",
                    "arguments": {"message": "ok"},
                },
            },
            headers,
        )
        names = [tool["name"] for tool in listed.get("result", {}).get("tools", [])]
        return {
            "compiled": True,
            "list": "testConversionTool" in names and "contractCustomTool" in names,
            "call": "error" not in generated
            and generated.get("result", {}).get("isError") is not True,
            "custom": "custom:ok" in json.dumps(custom),
        }
    finally:
        process.terminate()
        process.wait(timeout=10)
        server.shutdown()
        server.server_close()


def _probe(snapshot: Path, fixture_dir: Path) -> dict[str, object]:
    sys.path.insert(0, str(snapshot))
    from openapi_to_mcp.cli import cli  # noqa: PLC0415

    cli_manifest: dict[str, object] = {}
    for command_name, command in cli.commands.items():
        options: dict[str, object] = {}
        for parameter in command.params:
            if getattr(parameter, "opts", None):
                option = next(
                    (item for item in parameter.opts if item.startswith("--")),
                    parameter.opts[0],
                )
                options[option] = {
                    "required": bool(parameter.required),
                    "default": _jsonable(parameter.default),
                    "type": _option_type(parameter),
                }
        cli_manifest[command_name] = {"options": options}
    pyproject = tomllib.loads((snapshot / "pyproject.toml").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(
        prefix="release-contract-generated-"
    ) as raw_project:
        project = Path(raw_project)
        _run(
            [
                sys.executable,
                "-m",
                "openapi_to_mcp.cli",
                "generate",
                "--openapi-json",
                str(fixture_dir / "basic.yaml"),
                "--output-dir",
                str(project),
                "--transport",
                "stdio",
            ],
            cwd=snapshot,
        )
        _write_custom_tool(project / "src" / "custom" / "tools.ts")
        package = json.loads((project / "package.json").read_text(encoding="utf-8"))
        generated_source = (project / "src" / "runtime" / "generated.ts").read_text(
            encoding="utf-8"
        )
        match = re.search(
            r"export const tools = (\[.*?\]) as Tool\[\];", generated_source, re.DOTALL
        )
        if match is None:
            raise ValueError("generated tool manifest was not found")
        tools = {
            tool["name"]: tool.get("inputSchema", {})
            for tool in json.loads(match.group(1))
        }
        _run(["npm", "install", "--ignore-scripts"], cwd=project, timeout=300)
        _run(["npm", "run", "build"], cwd=project, timeout=180)
        runtime = {
            f"stdio_{name}": value
            for name, value in _run_stdio_contract(project).items()
        }
    with tempfile.TemporaryDirectory(prefix="release-contract-http-") as raw_http:
        project = Path(raw_http)
        http_port = _reserve_port()
        _run(
            [
                sys.executable,
                "-m",
                "openapi_to_mcp.cli",
                "generate",
                "--openapi-json",
                str(fixture_dir / "basic.yaml"),
                "--output-dir",
                str(project),
                "--transport",
                "streamable-http",
                "--port",
                str(http_port),
            ],
            cwd=snapshot,
        )
        _write_custom_tool(project / "src" / "custom" / "tools.ts")
        _run(["npm", "install", "--ignore-scripts"], cwd=project, timeout=300)
        _run(["npm", "run", "build"], cwd=project, timeout=180)
        runtime.update(
            {
                f"http_{name}": value
                for name, value in _run_http_contract(project, http_port).items()
            }
        )
    with tempfile.TemporaryDirectory(prefix="release-contract-auth-") as raw_auth:
        auth_project = Path(raw_auth)
        _run(
            [
                sys.executable,
                "-m",
                "openapi_to_mcp.cli",
                "generate",
                "--openapi-json",
                str(fixture_dir / "auth.yaml"),
                "--output-dir",
                str(auth_project),
                "--transport",
                "stdio",
            ],
            cwd=snapshot,
        )
        auth_env = sorted(
            re.findall(
                r"^(AUTH_[A-Z0-9_]+)=",
                (auth_project / ".env.example").read_text(encoding="utf-8"),
                re.MULTILINE,
            )
        )
    return {
        "cli": cli_manifest,
        "python_floor": pyproject["project"]["requires-python"],
        "node_floor": package["engines"]["node"],
        "generated": {"tools": tools, "auth_env": auth_env, "runtime": runtime},
    }


def _jsonable(value: object) -> object:
    try:
        json.dumps(value)
    except TypeError:
        return str(value)
    return value


def _option_type(parameter: object) -> dict[str, object]:
    option_type = parameter.type
    result: dict[str, object] = {"kind": str(option_type.name)}
    choices = getattr(option_type, "choices", None)
    if choices is not None:
        result["choices"] = sorted(str(choice) for choice in choices)
    for attribute in ("file_okay", "dir_okay", "exists"):
        value = getattr(option_type, attribute, None)
        if value is not None:
            result[attribute] = bool(value)
    return result


def _snapshot(repository: Path, revision: str, destination: Path) -> str:
    sha = _run(
        ["git", "rev-parse", "--verify", f"{revision}^{{commit}}"], cwd=repository
    ).stdout.strip()
    archive = destination.with_suffix(".tar")
    git = shutil.which("git")
    if git is None:
        raise ValueError("git is required to collect release contracts")
    with archive.open("wb") as output:
        subprocess.run(  # noqa: S603
            [git, "archive", sha],
            cwd=repository,
            stdout=output,
            check=True,
        )
    with tarfile.open(archive) as contents:
        contents.extractall(destination, filter="data")
    archive.unlink()
    return sha


def _collect(
    repository: Path, revision: str, fixture_dir: Path, script: Path
) -> tuple[str, dict[str, object]]:
    with tempfile.TemporaryDirectory(
        prefix="release-contract-snapshot-"
    ) as raw_snapshot:
        snapshot = Path(raw_snapshot)
        sha = _snapshot(repository, revision, snapshot)
        environment = {
            **os.environ,
            "UV_PROJECT_ENVIRONMENT": str(snapshot / ".release-contract-venv"),
        }
        uv = shutil.which("uv")
        if uv is None:
            raise ValueError("uv is required to collect release contracts")
        completed = subprocess.run(  # noqa: S603
            [
                uv,
                "run",
                "--directory",
                str(snapshot),
                "--frozen",
                "python",
                str(script),
                "--probe",
                "--snapshot",
                str(snapshot),
                "--fixtures",
                str(fixture_dir),
            ],
            cwd=repository,
            env=environment,
            text=True,
            capture_output=True,
            check=True,
            timeout=720,
        )
        return sha, json.loads(completed.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--fixtures", type=Path)
    args = parser.parse_args()
    if args.probe:
        if args.snapshot is None or args.fixtures is None:
            parser.error("--probe requires --snapshot and --fixtures")
        print(json.dumps(_probe(args.snapshot, args.fixtures), sort_keys=True))  # noqa: T201
        return 0
    if not args.base or not args.head or args.output is None:
        parser.error("--base, --head, and --output are required")
    script = Path(__file__).resolve()
    fixtures = script.parents[1] / "tests" / "resources" / "release_contracts"
    result: dict[str, object] = {
        "base_sha": args.base,
        "head_sha": args.head,
        "checks": {},
    }
    try:
        for fixture in FIXTURE_DIGESTS:
            _read_fixture(fixtures / fixture)
        base_sha, base_contract = _collect(Path.cwd(), args.base, fixtures, script)
        head_sha, head_contract = _collect(Path.cwd(), args.head, fixtures, script)
        result.update(compare_contracts(base_contract, head_contract))
        result["base_sha"] = base_sha
        result["head_sha"] = head_sha
        result["checks"] = {"base": base_contract, "head": head_contract}
    except (
        OSError,
        subprocess.SubprocessError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        result.update(
            {
                "minimum": "needs-review",
                "reasons": [f"evidence-unavailable:{error}"],
                "complete": False,
            }
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0 if result.get("complete") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
