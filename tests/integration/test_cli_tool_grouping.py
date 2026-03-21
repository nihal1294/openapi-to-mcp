from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

import yaml

from openapi_to_mcp.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import CliRunner


def _normalize_output(text: str) -> str:
    return " ".join(re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text).split())


def test_generate_applies_tag_prefix_grouping(
    runner: CliRunner, tmp_path: Path
) -> None:
    spec_path = _write_grouping_spec(tmp_path / "grouping.json")
    output_dir = tmp_path / "generated-grouped"

    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            str(spec_path),
            "--output-dir",
            str(output_dir),
            "--tool-grouping",
            "tag-prefix",
        ],
    )

    assert result.exit_code == 0
    assert _tool_names(output_dir) == ["pets_listPets", "orders_listOrders"]


def test_generate_policy_grouping_keeps_explicit_renames(
    runner: CliRunner, tmp_path: Path
) -> None:
    spec_path = _write_grouping_spec(tmp_path / "grouping.json")
    config_path = _write_policy(
        tmp_path / "mcpgen.yaml",
        {
            "generate": {"tool_grouping": "tag-prefix"},
            "tools": {"rename": {"names": {"listPets": "fetchPets"}}},
        },
    )
    output_dir = tmp_path / "generated-policy-grouped"

    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            str(spec_path),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    assert _tool_names(output_dir) == ["fetchPets", "orders_listOrders"]


def test_generate_cli_tool_grouping_overrides_policy_default(
    runner: CliRunner, tmp_path: Path
) -> None:
    spec_path = _write_grouping_spec(tmp_path / "grouping.json")
    config_path = _write_policy(
        tmp_path / "mcpgen.yaml",
        {"generate": {"tool_grouping": "tag-prefix"}},
    )
    output_dir = tmp_path / "generated-no-grouping"

    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            str(spec_path),
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
            "--tool-grouping",
            "none",
        ],
    )

    assert result.exit_code == 0
    assert _tool_names(output_dir) == ["listPets", "listOrders"]


def test_generate_fails_cleanly_on_grouping_name_collision(
    runner: CliRunner, tmp_path: Path
) -> None:
    spec_path = _write_collision_spec(tmp_path / "collision.json")
    output_dir = tmp_path / "generated-collision"

    result = runner.invoke(
        cli,
        [
            "generate",
            "--openapi-json",
            str(spec_path),
            "--output-dir",
            str(output_dir),
            "--tool-grouping",
            "tag-prefix",
        ],
    )

    assert result.exit_code != 0
    assert "Tool grouping produced duplicate tool name" in _normalize_output(
        result.output
    )


def _read_generated_source(output_dir: Path) -> str:
    return (output_dir / "src" / "runtime" / "generated.ts").read_text(encoding="utf-8")


def _tool_names(output_dir: Path) -> list[str]:
    generated_source = _read_generated_source(output_dir)
    match = re.search(
        r"export const tools = (?P<tools>\[.*?\]) as Tool\[\];",
        generated_source,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError(generated_source)
    tools = json.loads(match.group("tools"))
    return [tool["name"] for tool in tools]


def _write_grouping_spec(path: Path) -> Path:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Tool Grouping", "version": "1.0.0"},
        "servers": [{"url": "https://example.com/api"}],
        "paths": {
            "/pets": {
                "get": {
                    "tags": ["Pets"],
                    "operationId": "listPets",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/orders": {
                "get": {
                    "tags": ["Orders"],
                    "operationId": "listOrders",
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
    }
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path


def _write_collision_spec(path: Path) -> Path:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Tool Grouping Collision", "version": "1.0.0"},
        "servers": [{"url": "https://example.com/api"}],
        "paths": {
            "/pets": {
                "get": {
                    "tags": ["Pets"],
                    "operationId": "listPets",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/collision": {
                "get": {
                    "operationId": "pets_listPets",
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
    }
    path.write_text(json.dumps(spec), encoding="utf-8")
    return path


def _write_policy(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path
