"""Contracts for small pinned subsets of real public API descriptions."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import requests
from click.testing import CliRunner

from openapi_to_mcp.cli import cli

CORPUS = Path(__file__).parents[1] / "resources" / "compatibility_corpus"


@pytest.fixture(autouse=True)
def deny_python_network(monkeypatch) -> None:
    def blocked(*args, **kwargs):
        raise AssertionError("Provider network access is forbidden")

    monkeypatch.setattr(requests.sessions.Session, "request", blocked)


def _refs(value):
    if isinstance(value, dict):
        if "$ref" in value:
            yield value["$ref"]
        for child in value.values():
            yield from _refs(child)
    elif isinstance(value, list):
        for child in value:
            yield from _refs(child)


@pytest.mark.parametrize("name", ["github", "stripe"])
def test_fixture_integrity_and_local_references(name) -> None:
    manifest = json.loads((CORPUS / "manifest.json").read_text())["fixtures"][name]
    data = (CORPUS / f"{name}.json").read_bytes()
    assert hashlib.sha256(data).hexdigest() == manifest["subset_sha256"]
    assert (
        hashlib.sha256((CORPUS / f"{name}-LICENSE").read_bytes()).hexdigest()
        == manifest["license_sha256"]
    )
    spec = json.loads(data)
    for ref in _refs(spec):
        assert ref.startswith("#/")
        target = spec
        for part in ref[2:].split("/"):
            target = target[part.replace("~1", "/").replace("~0", "~")]
        assert target is not None
    actual = {f"GET {path}" for path, item in spec["paths"].items() if "get" in item}
    assert actual == set(manifest["operations"])


@pytest.mark.parametrize("name", ["github", "stripe"])
def test_doctor(name) -> None:
    result = CliRunner().invoke(
        cli, ["doctor", "-o", str(CORPUS / f"{name}.json"), "--format", "json"]
    )
    report = json.loads(result.stdout[result.stdout.index("{\n") :])
    assert report["errors"] == 0
    if name == "stripe":
        assert result.exit_code == 2
        assert {(i["code"], i["location"]) for i in report["issues"]} == {
            ("risky_union_schema", "paths./v2/core/events.get"),
            ("risky_union_schema", "paths./v2/core/events/{id}.get"),
        }
    else:
        # Future doctor versions may add advisory warnings, including name checks.
        assert result.exit_code in (0, 2)


@pytest.mark.parametrize(
    ("name", "transport"),
    [
        ("github", "stdio"),
        ("github", "streamable-http"),
        ("stripe", "stdio"),
        ("stripe", "streamable-http"),
    ],
)
def test_generation_and_build(name, transport, tmp_path) -> None:
    output = tmp_path / "server"
    spec = json.loads((CORPUS / f"{name}.json").read_text())
    result = CliRunner().invoke(
        cli,
        [
            "generate",
            "-o",
            str(CORPUS / f"{name}.json"),
            "-d",
            str(output),
            "--transport",
            transport,
        ],
    )
    assert result.exit_code == 0, result.output
    report = json.loads((output / "generation_report.json").read_text())
    assert report["mapped_tools"] == 2
    assert report["skipped_operations"] == []
    source = (output / "src/runtime/generated.ts").read_text()
    tools = json.loads(
        re.search(
            r"export const tools = (\[.*?\]) as Tool\[\];", source, re.DOTALL
        ).group(1)
    )
    runtime = json.loads(
        re.search(
            r"export const toolRuntimeData = (\{.*?\}) as Record<", source, re.DOTALL
        ).group(1)
    )
    tools = {tool["name"]: tool for tool in tools}
    if name == "github":
        assert (
            spec["paths"]["/repos/{owner}/{repo}"]["get"]["operationId"] == "repos/get"
        )
        assert set(tools) == {"repos/get", "meta/get-zen"}
        repo = tools["repos/get"]
        assert set(repo["inputSchema"]["required"]) == {"owner", "repo"}
        assert all(
            repo["inputSchema"]["properties"][p]["type"] == "string"
            for p in ("owner", "repo")
        )
        assert repo["outputSchema"]["type"] == "object"
        assert "full_name" in repo["outputSchema"]["required"]
        assert "outputSchema" not in tools["meta/get-zen"]
        assert runtime["repos/get"]["path"] == "/repos/{owner}/{repo}"
        assert runtime["repos/get"]["security"] is None
    else:
        assert (
            spec["paths"]["/v2/core/events"]["get"]["operationId"] == "GetV2CoreEvents"
        )
        assert set(tools) == {"GetV2CoreEvents", "GetV2CoreEventsId"}
        listing = tools["GetV2CoreEvents"]
        props = listing["inputSchema"]["properties"]
        assert props["limit"]["type"] == "integer"
        assert props["created"]["type"] == "object"
        assert props["types"]["items"]["type"] == "string"
        assert listing["outputSchema"]["type"] == "object"
        assert "data" in listing["outputSchema"]["required"]
        detail = tools["GetV2CoreEventsId"]
        assert detail["inputSchema"]["required"] == ["id"]
        assert detail["inputSchema"]["properties"]["id"]["type"] == "string"
        assert {"id", "type"} <= set(detail["outputSchema"]["required"])
        assert runtime["GetV2CoreEventsId"]["path"] == "/v2/core/events/{id}"
        assert runtime["GetV2CoreEvents"]["security"] == [
            {"basicAuth": []},
            {"bearerAuth": []},
        ]
        params = {p["name"]: p for p in runtime["GetV2CoreEvents"]["parameters"]}
        assert params["created"]["style"] == params["types"]["style"] == "deepObject"
        env = (output / ".env.example").read_text()
        assert all(
            f"{key}=" in env
            for key in (
                "AUTH_BASICAUTH_USERNAME",
                "AUTH_BASICAUTH_PASSWORD",
                "AUTH_BEARERAUTH_TOKEN",
            )
        )
    npm = shutil.which("npm")
    assert npm is not None, "npm is required for generated server builds"
    for args in (
        ["install", "--ignore-scripts", "--no-audit", "--no-fund"],
        ["run", "build"],
    ):
        proc = subprocess.run(  # noqa: S603
            [npm, *args],
            cwd=output,
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
