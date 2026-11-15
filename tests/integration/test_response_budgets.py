"""Exercise generated response limits against real loopback streams."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.integration.basic_auth_support import basic_project as basic_project  # noqa: PLC0414
from tests.integration.basic_auth_support import build_basic_project


def run_case(project: Path, scenario: dict) -> tuple[dict, str]:
    # Reuse the generated-project runner with a dedicated stream fixture.
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("MCP_", "TARGET_API_", "AUTH_"))
    }
    env.pop("FORCE_COLOR", None)
    env.pop("CLICOLOR_FORCE", None)
    env.update(TERM="dumb", NO_COLOR="1")
    script = Path(__file__).parents[1] / "resources/response_budget_request.mjs"
    node = shutil.which("node")
    assert node is not None
    result = subprocess.run(  # noqa: S603
        [node, str(script), str(project)],
        input=json.dumps(scenario),
        text=True,
        capture_output=True,
        env=env,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout), result.stderr


@pytest.mark.parametrize(
    ("body", "content_type"),
    [
        ('{"a":"é"}', "application/json"),
        ("plain", "text/plain"),
        ("42", "application/json"),
        ("{bad", "application/json"),
    ],
)
def test_admitted_matches_unbounded(
    basic_project: Path, body: str, content_type: str
) -> None:
    base = {"body": body, "contentType": content_type, "chunked": True}
    baseline, _ = run_case(basic_project, base)
    bounded, _ = run_case(
        basic_project,
        {**base, "env": {"MCP_MAX_RESPONSE_BYTES": str(len(body.encode()))}},
    )
    for result in (baseline["results"][0], bounded["results"][0]):
        result.pop("_meta")
    assert bounded["results"] == baseline["results"]


@pytest.mark.parametrize(
    ("gzip", "known"), [(False, True), (False, False), (True, True)]
)
def test_oversize_no_retry_cache_or_body_audit(
    basic_project: Path,
    gzip: bool,  # noqa: FBT001
    known: bool,  # noqa: FBT001
) -> None:
    body = '{"secret":"' + "z" * 10000 + '"}'
    capture, logs = run_case(
        basic_project,
        {
            "body": body,
            "gzip": gzip,
            "knownLength": known,
            "calls": 2,
            "env": {
                "MCP_MAX_RESPONSE_BYTES": "10",
                "MCP_CACHE_TTL_MS": "10000",
                "MCP_RETRY_MAX_RETRIES": "2",
                "MCP_RETRY_BUDGET_PER_MINUTE": "10",
            },
        },
    )
    assert capture["requests"] == 2
    for result in capture["results"]:
        assert result["isError"]
        assert result["_meta"]["error"] == {
            "code": "response_too_large",
            "source": "upstream",
            "retryable": False,
        }
        assert (
            result["content"][0]["text"]
            == "Upstream response exceeds configured byte limit."
        )
        assert "structuredContent" not in result
    assert "zzzzzz" not in logs


def test_global_ceiling_and_per_tool_tightening(basic_project: Path) -> None:
    for global_limit, tool_limit, rejected in [
        (10, 0, True),
        (0, 10, True),
        (20, 10, True),
        (10, 20, True),
        (0, 0, False),
        (20, 20, False),
    ]:
        capture, _ = run_case(
            basic_project,
            {
                "body": "abcdefghijkl",
                "execution": {"maxResponseBytes": tool_limit},
                "env": {"MCP_MAX_RESPONSE_BYTES": str(global_limit)},
            },
        )
        assert bool(capture["results"][0].get("isError")) is rejected


def test_slow_body_times_out(basic_project: Path) -> None:
    capture, _ = run_case(
        basic_project,
        {
            "body": "123456",
            "slow": True,
            "env": {"MCP_MAX_RESPONSE_BYTES": "100", "MCP_TOOL_TIMEOUT_MS": "50"},
        },
    )
    assert capture["results"][0]["_meta"]["error"]["code"] == "tool_timeout"
    assert capture["closed"]


def test_error_response_and_cache(basic_project: Path) -> None:
    error, _ = run_case(
        basic_project,
        {
            "body": '{"message":"no"}',
            "status": 400,
            "env": {"MCP_MAX_RESPONSE_BYTES": "100"},
        },
    )
    assert error["results"][0]["_meta"]["error"]["code"] == "api_bad_request"
    assert "no" in error["results"][0]["content"][0]["text"]
    cached, _ = run_case(
        basic_project,
        {
            "body": '{"ok":true}',
            "calls": 2,
            "env": {"MCP_MAX_RESPONSE_BYTES": "100", "MCP_CACHE_TTL_MS": "10000"},
        },
    )
    assert cached["requests"] == 1


@pytest.mark.parametrize("raw", ["-1", "1.5", "1foo", "9007199254740992"])
def test_invalid_global_limit_fails_startup(basic_project: Path, raw: str) -> None:
    node = shutil.which("node")
    assert node is not None
    env = os.environ.copy()
    env.update(TARGET_API_BASE_URL="http://127.0.0.1", MCP_MAX_RESPONSE_BYTES=raw)
    result = subprocess.run(  # noqa: S603
        [node, "--input-type=module", "-e", "import './build/runtime/config.js'"],
        cwd=basic_project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode != 0
    assert "MCP_MAX_RESPONSE_BYTES must be a safe integer" in result.stderr


@pytest.mark.parametrize("value", [-1, 1.5, True, 9007199254740992])
def test_invalid_policy_limit(value: object) -> None:
    from openapi_to_mcp.common.exceptions import PolicyConfigError  # noqa: PLC0415
    from openapi_to_mcp.policy.parser import _parse_execution_override  # noqa: PLC0415

    with pytest.raises(PolicyConfigError):
        _parse_execution_override({"max_response_bytes": value}, "execution")


def test_one_byte_above_and_error_body_rejected(basic_project: Path) -> None:
    for status in (200, 400):
        capture, _ = run_case(
            basic_project,
            {
                "body": "éé",
                "status": status,
                "env": {"MCP_MAX_RESPONSE_BYTES": "3"},
            },
        )
        assert capture["results"][0]["_meta"]["error"]["code"] == "response_too_large"


def test_large_stream_stops_early(basic_project: Path) -> None:
    capture, _ = run_case(
        basic_project,
        {
            "longStream": True,
            "env": {"MCP_MAX_RESPONSE_BYTES": "1024"},
        },
    )
    assert capture["results"][0]["_meta"]["error"]["code"] == "response_too_large"
    assert capture["closed"]
    assert capture["chunksSent"] < 100


def test_run_option_and_policy_metadata() -> None:
    from click.testing import CliRunner  # noqa: PLC0415

    from openapi_to_mcp.cli import cli  # noqa: PLC0415
    from openapi_to_mcp.commands.runtime_overrides import build_runtime_override_env  # noqa: PLC0415
    from openapi_to_mcp.policy.parser import _parse_execution_override  # noqa: PLC0415

    assert build_runtime_override_env({"max_response_bytes": 0}) == {
        "MCP_MAX_RESPONSE_BYTES": "0"
    }
    assert (
        _parse_execution_override(
            {"max_response_bytes": 0}, "execution"
        ).max_response_bytes
        == 0
    )
    for raw in ("-1", "1.5", "9007199254740992"):
        result = CliRunner().invoke(cli, ["run", "--max-response-bytes", raw])
        assert result.exit_code != 0
        assert "max-response-bytes" in result.output


def test_bounded_response_follows_existing_redirect(basic_project: Path) -> None:
    capture, _ = run_case(
        basic_project,
        {
            "body": '{"ok":true}',
            "redirect": True,
            "env": {"MCP_MAX_RESPONSE_BYTES": "20"},
        },
    )
    assert capture["requests"] == 2
    assert capture["results"][0]["structuredContent"] == {"ok": True}


@pytest.fixture(scope="module", params=["1.20.0", "1.21.1"])
def interruption_project(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    output = build_basic_project(
        tmp_path_factory.mktemp("interrupted-response") / "generated"
    )
    from click.testing import CliRunner  # noqa: PLC0415

    from openapi_to_mcp.cli import cli  # noqa: PLC0415

    generated = CliRunner().invoke(
        cli,
        [
            "generate",
            "-o",
            str(output.parent / "basic.json"),
            "--output-dir",
            str(output),
            "--transport",
            "stdio",
        ],
    )
    assert generated.exit_code == 0, generated.output
    npm = shutil.which("npm")
    assert npm is not None
    result = subprocess.run(  # noqa: S603
        [
            npm,
            "install",
            "--ignore-scripts",
            "--no-audit",
            "--no-fund",
            "--no-save",
            f"axios@{request.param}",
        ],
        cwd=output,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    built = subprocess.run(  # noqa: S603
        [npm, "run", "build"],
        cwd=output,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    return output


@pytest.mark.parametrize(
    ("interrupt", "status"),
    [("once", 200), ("always", 200), ("once", 503), ("always", 503)],
)
def test_interrupted_response_retries_match_unbounded(
    interruption_project: Path, interrupt: str, status: int
) -> None:
    captures = []
    for limit in ("0", "100"):
        capture, logs = run_case(
            interruption_project,
            {
                "body": '{"ok":true}',
                "interrupt": interrupt,
                "protocol": True,
                "interruptStatus": status,
                "env": {
                    "MCP_MAX_RESPONSE_BYTES": limit,
                    "MCP_RETRY_MAX_RETRIES": "2",
                    "MCP_RETRY_BUDGET_PER_MINUTE": "10",
                },
            },
        )
        assert "INTERRUPTED_RESPONSE_BODY_SENTINEL" not in logs
        captures.append(capture)
    expected_attempts = 1 if status == 200 else 2 if interrupt == "once" else 3
    assert [capture["requests"] for capture in captures] == [
        expected_attempts,
        expected_attempts,
    ]
    if status == 503 and interrupt == "once":
        for capture in captures:
            assert capture["results"][0]["structuredContent"] == {"ok": True}
    else:
        results = [capture["results"][0] for capture in captures]
        assert results[0]["_meta"]["error"] == results[1]["_meta"]["error"]
        assert results[0]["isError"]
        assert results[1]["isError"]
        assert "structuredContent" not in results[1]
