from __future__ import annotations

import json

from openapi_to_mcp.cli import cli


def test_policy_metadata_and_execution_are_review_changes(runner, tmp_path) -> None:
    spec = tmp_path / "spec.json"
    spec.write_text(
        json.dumps(
            {
                "openapi": "3.0.0",
                "info": {"title": "T", "version": "1"},
                "paths": {
                    "/pets": {
                        "get": {
                            "operationId": "listPets",
                            "summary": "List pets",
                            "responses": {"200": {"description": "OK"}},
                        }
                    }
                },
            }
        )
    )
    policy = tmp_path / "policy.yaml"
    policy.write_text(
        """tools:\n  descriptions:\n    names:\n      listPets: changed\n  annotations:\n    names:\n      listPets:\n        read_only: true\nexecution:\n  names:\n    listPets:\n      timeout_ms: 123\n"""
    )
    result = runner.invoke(
        cli,
        [
            "diff",
            "-b",
            str(spec),
            "-a",
            str(spec),
            "--after-config",
            str(policy),
            "--format",
            "json",
            "--fail-on",
            "review",
        ],
    )
    assert result.exit_code == 2, result.output
    report = json.loads(result.stdout)
    assert report["review"] == 3
    assert {c["code"] for c in report["changes"]} == {
        "description_changed",
        "annotations_changed",
        "execution_changed",
    }


def test_independent_selection_grouping_and_no_discovery(
    runner, tmp_path, monkeypatch
) -> None:
    spec = tmp_path / "spec.json"
    spec.write_text(
        json.dumps(
            {
                "openapi": "3.0.0",
                "info": {"title": "T", "version": "1"},
                "paths": {
                    "/pets": {
                        "get": {
                            "operationId": "listPets",
                            "tags": ["Pets"],
                            "responses": {"200": {"description": "OK"}},
                        }
                    }
                },
            }
        )
    )
    (tmp_path / "mcpgen.yaml").write_text(
        'tools:\n  exclude:\n    operations: ["GET /pets"]\n'
    )
    policy = tmp_path / "other.yaml"
    policy.write_text("generate:\n  tool_grouping: tag-prefix\n")
    monkeypatch.chdir(tmp_path)
    base = ["diff", "-b", str(spec), "-a", str(spec), "--format", "json"]
    result = runner.invoke(cli, base)
    assert json.loads(result.stdout)["changes"] == []
    result = runner.invoke(cli, [*base, "--after-config", str(policy)])
    assert [c["code"] for c in json.loads(result.stdout)["changes"]] == ["tool_renamed"]
    result = runner.invoke(
        cli, [*base, "--after-config", str(policy), "--after-tool-grouping", "none"]
    )
    assert json.loads(result.stdout)["changes"] == []
    result = runner.invoke(
        cli, [*base, "--before-config", str(policy), "--before-no-config"]
    )
    assert result.exit_code != 0
    result = runner.invoke(
        cli,
        [
            *base,
            "--before-config",
            str(tmp_path / "mcpgen.yaml"),
            "--fail-on",
            "review",
        ],
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout)["changes"][0]["code"] == "tool_added"


def test_auth_change_does_not_print_values(runner, tmp_path) -> None:
    spec = tmp_path / "spec.json"
    spec.write_text(
        json.dumps(
            {
                "openapi": "3.0.0",
                "info": {"title": "T", "version": "1"},
                "paths": {
                    "/pets": {
                        "get": {
                            "operationId": "listPets",
                            "responses": {"200": {"description": "OK"}},
                        }
                    }
                },
            }
        )
    )
    policy = tmp_path / "policy.yaml"
    policy.write_text(
        "auth:\n  names:\n    listPets:\n      security_schemes:\n        secret:\n          type: apiKey\n          in: header\n          name: SECRET_VALUE_123\n      security:\n        - secret: []\n"
    )
    for fmt in ("json", "text"):
        result = runner.invoke(
            cli,
            [
                "diff",
                "-b",
                str(spec),
                "-a",
                str(spec),
                "--after-config",
                str(policy),
                "--format",
                fmt,
                "--fail-on",
                "breaking",
            ],
        )
        assert result.exit_code == 2, result.output
        assert "auth_changed" in result.output
        assert "SECRET_VALUE_123" not in result.output


def test_mapping_errors_and_policy_errors_never_produce_report(
    runner, tmp_path
) -> None:
    source = tmp_path / "swagger.json"
    source.write_text(
        json.dumps(
            {
                "swagger": "2.0",
                "info": {"title": "T", "version": "1"},
                "paths": {
                    "/bad": {
                        "get": {
                            "operationId": "bad",
                            "parameters": [
                                {
                                    "name": "q",
                                    "in": "body",
                                    "schema": {"type": "object"},
                                }
                            ],
                            "responses": {"200": {"description": "OK"}},
                        }
                    }
                },
            }
        )
    )
    config = tmp_path / "policy.yaml"
    config.write_text(
        "generate:\n  strict: false\n  on_mapping_error: skip\n  on_schema_error: skip\n"
    )
    base = ["diff", "-b", str(source), "-a", str(source), "--format", "json"]
    for args in ([], ["--before-config", str(config)], ["--after-config", str(config)]):
        result = runner.invoke(cli, [*base, *args])
        assert result.exit_code == 1
        assert not result.stdout.strip()
    config.write_text("tools: [invalid]")
    result = runner.invoke(cli, [*base, "--after-config", str(config)])
    assert result.exit_code == 1
    assert not result.stdout.strip()


def test_name_warnings_do_not_pollute_json_and_validate_is_fatal(
    runner, tmp_path
) -> None:
    spec = tmp_path / "spec.json"
    spec.write_text(
        json.dumps(
            {
                "openapi": "3.0.0",
                "info": {"title": "T", "version": "1"},
                "paths": {
                    "/pets": {
                        "get": {
                            "operationId": "bad name",
                            "responses": {"200": {"description": "OK"}},
                        }
                    }
                },
            }
        )
    )
    base = ["diff", "-b", str(spec), "-a", str(spec), "--format", "json"]
    result = runner.invoke(cli, base)
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["changes"] == []
    result = runner.invoke(cli, [*base, "--after-tool-name-policy", "validate"])
    assert result.exit_code == 1
    assert not result.stdout.strip()


def test_false_annotation_and_zero_execution_are_distinct_from_absence(
    runner, tmp_path
) -> None:
    spec = tmp_path / "spec.json"
    spec.write_text(
        json.dumps(
            {
                "openapi": "3.0.0",
                "info": {"title": "T", "version": "1"},
                "paths": {
                    "/pets": {
                        "get": {
                            "operationId": "listPets",
                            "responses": {"200": {"description": "OK"}},
                        }
                    }
                },
            }
        )
    )
    policy = tmp_path / "policy.yaml"
    policy.write_text(
        "tools:\n  annotations:\n    names:\n      listPets:\n        read_only: false\nexecution:\n  names:\n    listPets:\n      cache_ttl_ms: 0\n"
    )
    base = [
        "diff",
        "-b",
        str(spec),
        "-a",
        str(spec),
        "--after-config",
        str(policy),
        "--format",
        "json",
    ]
    for mode, exit_code in [("none", 0), ("breaking", 0), ("review", 2)]:
        result = runner.invoke(cli, [*base, "--fail-on", mode])
        assert result.exit_code == exit_code, result.output
        report = json.loads(result.stdout)
        assert report["review"] == 2
        assert {c["code"] for c in report["changes"]} == {
            "annotations_changed",
            "execution_changed",
        }
        assert next(c for c in report["changes"] if c["code"] == "execution_changed")[
            "details"
        ]["fields"] == ["cacheTtlMs"]


def test_mapper_warning_keeps_json_stdout_clean(runner, tmp_path) -> None:
    spec = tmp_path / "spec.json"
    spec.write_text(
        json.dumps(
            {
                "openapi": "3.0.0",
                "info": {"title": "T", "version": "1"},
                "paths": {
                    "/pets": {
                        "post": {
                            "operationId": "createPet",
                            "requestBody": {"required": True, "content": {}},
                            "responses": {"200": {"description": "OK"}},
                        }
                    }
                },
            }
        )
    )
    result = runner.invoke(
        cli, ["diff", "-b", str(spec), "-a", str(spec), "--format", "json"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["changes"] == []
    assert "no valid schema" in result.stderr
