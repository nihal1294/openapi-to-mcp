"""Build and exercise a generated HTTP server over loopback sockets."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import requests
from click.testing import CliRunner

from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from collections.abc import Iterator


def build_http_server(output: Path) -> Path:
    spec = Path(__file__).parents[2] / "examples/container/openapi.yaml"
    result = CliRunner().invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            str(spec),
            "--output-dir",
            str(output),
            "--mcp-server-name",
            "health-probe-test",
            "--transport",
            "streamable-http",
        ],
    )
    assert result.exit_code == 0, result.output
    npm = shutil.which("npm")
    assert npm is not None, "npm is required for generated HTTP integration tests"
    subprocess.run(  # noqa: S603
        [npm, "install", "--ignore-scripts", "--no-audit", "--no-fund"],
        cwd=output,
        check=True,
        capture_output=True,
        text=True,
    )
    compiled = subprocess.run(  # noqa: S603
        [npm, "run", "build"], cwd=output, capture_output=True, text=True, check=False
    )
    assert compiled.returncode == 0, compiled.stdout + compiled.stderr
    return output


def available_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def launch_server(output: Path, **overrides: str) -> tuple[subprocess.Popen, str]:
    node = shutil.which("node")
    assert node is not None
    port = available_port()
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("MCP_", "AUTH_", "TARGET_API_"))
    }
    env.update(
        TARGET_API_BASE_URL="http://127.0.0.1:9",
        MCP_HTTP_HOST="127.0.0.1",
        MCP_HTTP_PORT=str(port),
        MCP_HTTP_ENDPOINT="/mcp",
        MCP_ALLOWED_HOSTS="127.0.0.1,localhost",
        MCP_ALLOWED_ORIGINS="http://localhost",
    )
    env.update(overrides)
    process = subprocess.Popen(  # noqa: S603
        [node, "build/index.js"],
        cwd=output,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return process, f"http://127.0.0.1:{port}"


def stop_server(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            raise AssertionError(
                "Generated HTTP server did not stop on SIGTERM"
            ) from None
    process.communicate(timeout=5)


@contextmanager
def running_server(
    output: Path, **overrides: str
) -> Iterator[tuple[str, subprocess.Popen]]:
    process, base = launch_server(output, **overrides)
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                raise AssertionError(f"Generated server exited: {stdout}\n{stderr}")
            try:
                requests.get(base + "/", timeout=0.2)
                break
            except requests.ConnectionError:
                time.sleep(0.05)
        else:
            raise AssertionError("Generated server did not start its HTTP listener")
        yield base, process
    finally:
        stop_server(process)
