"""Exercise cancellation through the compiled generated runtime."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from openapi_to_mcp.cli import cli
from tests.integration.basic_auth_support import basic_project as basic_project  # noqa: PLC0414
from tests.integration.basic_auth_support import basic_spec


@pytest.fixture(scope="module")
def stdio_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("cancellation-stdio")
    spec = root / "spec.json"
    spec.write_text(json.dumps(basic_spec()), encoding="utf-8")
    output = root / "generated"
    result = CliRunner().invoke(
        cli,
        [
            "generate",
            "-o",
            str(spec),
            "--output-dir",
            str(output),
            "--transport",
            "stdio",
        ],
    )
    assert result.exit_code == 0, result.output
    (output / "src/custom/tools.ts").write_text(
        """import type { CustomToolDefinition } from '../runtime/generated.js';
let started = false;
let cancelled = false;
export function getCustomTools(): CustomToolDefinition[] {
  const tool = (name: string) => ({ name, description: name, inputSchema: { type: 'object' as const } });
  return [
    { tool: tool('legacy'), handler: async (_args) => ({ content: [{ type: 'text', text: 'legacy' }] }) },
    { tool: tool('cooperative'), handler: async (_args, { signal }) => {
      started = true;
      await new Promise<void>((resolve) => signal.addEventListener('abort', () => { cancelled = true; resolve(); }, { once: true }));
      return { content: [{ type: 'text', text: 'done' }] };
    } },
    { tool: tool('status'), handler: async (_args) => ({ content: [{ type: 'text', text: JSON.stringify({ started, cancelled }) }] }) },
  ];
}
""",
        encoding="utf-8",
    )
    npm = shutil.which("npm")
    assert npm is not None
    for args in (
        ["install", "--ignore-scripts", "--no-audit", "--no-fund"],
        ["run", "build"],
    ):
        process = subprocess.run(  # noqa: S603
            [npm, *args],
            cwd=output,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        assert process.returncode == 0, process.stdout + process.stderr
    return output


def test_cancellation_releases_permits_and_aborts_requests(basic_project: Path) -> None:
    node = shutil.which("node")
    assert node is not None
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("MCP_", "TARGET_API_", "AUTH_"))
    }
    script = Path(__file__).parents[1] / "resources/cancellation_request.mjs"
    result = subprocess.run(  # noqa: S603
        [node, str(script), str(basic_project)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "cancellation checks passed" in result.stdout


def test_stdio_cancellation_reaches_runtime(stdio_project: Path) -> None:
    node = shutil.which("node")
    assert node is not None
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("MCP_", "TARGET_API_", "AUTH_"))
    }
    script = Path(__file__).parents[1] / "resources/cancellation_stdio.mjs"
    result = subprocess.run(  # noqa: S603
        [node, str(script), str(stdio_project)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "stdio cancellation passed" in result.stdout


def test_modern_http_cancellation_reaches_runtime(basic_project: Path) -> None:
    node = shutil.which("node")
    assert node is not None
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("MCP_", "TARGET_API_", "AUTH_"))
    }
    script = Path(__file__).parents[1] / "resources/cancellation_modern_http.mjs"
    result = subprocess.run(  # noqa: S603
        [node, str(script), str(basic_project)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "modern HTTP cancellation passed" in result.stdout
