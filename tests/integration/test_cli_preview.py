import json
import re

import yaml
from click.testing import CliRunner

from openapi_to_mcp.cli import cli
from openapi_to_mcp.commands.generation_models import GenerationBehavior
from openapi_to_mcp.mapping.preparation import prepare_tools
from openapi_to_mcp.policy import load_policy_config


def test_preview_json_reports_public_catalog() -> None:
    result = CliRunner().invoke(
        cli, ["preview", "-o", "tests/resources/test_openapi.yaml", "--format", "json"]
    )
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert report["schema_version"] == 1
    assert report["tools"]
    encoded = json.dumps(
        report["tools"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    assert report["catalog"]["total_bytes"] == len(encoded)


def test_preview_matches_generated_tools_with_policy_and_grouping(
    tmp_path, runner
) -> None:
    source = tmp_path / "spec.json"
    source.write_text(
        json.dumps(
            {
                "openapi": "3.0.0",
                "info": {"title": "test", "version": "1"},
                "paths": {
                    "/a": {
                        "get": {
                            "operationId": "alpha",
                            "tags": ["Péts"],
                            "summary": "café",
                            "responses": {"200": {"description": "ok"}},
                        }
                    },
                    "/b": {
                        "get": {
                            "operationId": "beta",
                            "tags": ["Pets"],
                            "responses": {"200": {"description": "ok"}},
                        }
                    },
                },
            }
        )
    )
    policy = tmp_path / "policy.yaml"
    policy.write_text(
        yaml.safe_dump(
            {
                "generate": {
                    "tool_descriptions": "method",
                    "tool_grouping": "tag-prefix",
                },
                "tools": {
                    "rename": {"operations": {"GET /a": "renamed"}},
                    "descriptions": {
                        "operations": {"GET /a": "chosen"},
                        "names": {"alpha": "ignored", "renamed": "also ignored"},
                    },
                },
            }
        )
    )
    args = ["-o", str(source), "--config", str(policy)]
    generated = tmp_path / "generated"
    gen = runner.invoke(cli, ["generate", *args, "-d", str(generated)])
    assert gen.exit_code == 0, gen.output
    preview = runner.invoke(cli, ["preview", *args, "--format", "json"])
    assert preview.exit_code == 0, preview.output
    report = json.loads(preview.stdout)
    content = (generated / "src/runtime/generated.ts").read_text()
    tools = json.loads(
        re.search(
            r"export const tools = (\[.*?\]) as Tool\[\];", content, re.DOTALL
        ).group(1)
    )
    assert report["tools"] == tools
    assert [tool["name"] for tool in tools] == ["renamed", "pets_beta"]
    decisions = report["operations"][0]["decisions"]
    assert {
        "kind": "description_override",
        "match": "operation",
        "key": "GET /a",
    } in decisions
    assert {"kind": "grouping", "reason": "policy_rename", "prefix": None} in decisions


def test_empty_catalog_limits_and_cli_precedence(tmp_path, runner) -> None:
    policy = tmp_path / "policy.yaml"
    policy.write_text(
        yaml.safe_dump(
            {
                "generate": {"tool_descriptions": "method"},
                "tools": {"include": {"names": ["no-match"]}},
            }
        )
    )
    args = [
        "preview",
        "-o",
        "tests/resources/test_openapi.yaml",
        "--config",
        str(policy),
        "--format",
        "json",
        "--tool-descriptions",
        "spec",
    ]
    equal = runner.invoke(cli, [*args, "--max-catalog-bytes", "2"])
    assert equal.exit_code == 0, equal.output
    report = json.loads(equal.stdout)
    assert report["catalog"]["total_bytes"] == 2
    assert report["tools"] == []
    assert report["settings"]["tool_descriptions"] == "spec"
    assert all(row["status"] == "mapped_then_excluded" for row in report["operations"])
    over = runner.invoke(cli, [*args, "--max-catalog-bytes", "1"])
    assert over.exit_code == 2
    assert json.loads(over.stdout)["catalog"]["total_bytes"] == 2


def test_skip_json_is_clean_and_strict_is_error(tmp_path, runner) -> None:
    spec = {
        "swagger": "2.0",
        "info": {"title": "test", "version": "1"},
        "paths": {
            "/bad": {
                "get": {
                    "operationId": "bad",
                    "parameters": [
                        {"name": "q", "in": "body", "schema": {"type": "object"}}
                    ],
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }
    source = tmp_path / "spec.json"
    source.write_text(json.dumps(spec))
    args = ["preview", "-o", str(source), "--format", "json"]
    strict = runner.invoke(cli, args)
    assert strict.exit_code != 0
    assert not strict.stdout.strip()
    skip = runner.invoke(cli, [*args, "--no-strict"])
    assert skip.exit_code == 0, skip.output
    report = json.loads(skip.stdout)
    assert report["operations"][0]["status"] == "skipped"
    assert report["skipped_operations"]
    text_result = runner.invoke(cli, ["preview", "-o", str(source), "--no-strict"])
    assert text_result.exit_code == 0, text_result.output
    assert 'GET "/bad": skipped; "bad"' in text_result.stdout
    assert "mapping skipped:" in text_result.stdout
    assert "unsupported Swagger 2 construct" in text_result.stdout


def test_trace_preserves_swagger_name_allocation_and_secret_boundary(
    tmp_path, runner, monkeypatch
) -> None:
    spec = {
        "swagger": "2.0",
        "info": {"title": "test", "version": "1"},
        "paths": {
            "/pets-by-id": {"get": {"responses": {"200": {"description": "ok"}}}},
            "/pets_by_id": {
                "get": {
                    "parameters": [
                        {"name": "payload", "in": "body", "schema": {"type": "object"}}
                    ],
                    "responses": {"200": {"description": "ok"}},
                }
            },
            "/pets.by.id": {"get": {"responses": {"200": {"description": "ok"}}}},
        },
    }
    source = tmp_path / "spec.json"
    source.write_text(json.dumps(spec))
    policy_file = tmp_path / "policy.yaml"
    policy_file.write_text(
        yaml.safe_dump(
            {
                "auth": {
                    "operations": {
                        "GET /pets-by-id": {
                            "security": [{"secret-scheme": []}],
                            "security_schemes": {
                                "secret-scheme": {
                                    "type": "apiKey",
                                    "in": "header",
                                    "name": "hidden-secret-value",
                                }
                            },
                        }
                    }
                }
            }
        )
    )
    policy = load_policy_config(str(policy_file))
    behavior = GenerationBehavior(
        tool_grouping="none",
        telemetry="off",
        strict=False,
        runtime_validation="input",
        on_mapping_error=None,
        on_schema_error=None,
    )
    plain = prepare_tools(spec, behavior=behavior, policy=policy)
    traced = prepare_tools(spec, behavior=behavior, policy=policy, trace=True)
    assert plain.public_tools == traced.public_tools
    assert plain.report == traced.report
    assert [row["provisional_name"] for row in traced.trace] == [
        "get_pets_by_id",
        "get_pets_by_id_2",
        "get_pets_by_id_2",
    ]
    assert [row["status"] for row in traced.trace] == [
        "selected",
        "skipped",
        "selected",
    ]
    monkeypatch.setenv("AUTH_SECRET_SCHEME_API_KEY", "environment-secret-value")
    result = runner.invoke(
        cli,
        [
            "preview",
            "-o",
            str(source),
            "--config",
            str(policy_file),
            "--no-strict",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "hidden-secret-value" not in result.output
    assert "environment-secret-value" not in result.output
    assert {
        "kind": "auth_override",
        "match": "operation",
        "key": "GET /pets-by-id",
    } in json.loads(result.stdout)["operations"][0]["decisions"]


def test_early_exclusion_and_ordinary_exclusion_follow_actual_branches(
    tmp_path,
) -> None:
    spec = {
        "openapi": "3.2.0",
        "info": {"title": "test", "version": "1"},
        "paths": {
            "/early": {
                "get": {
                    "operationId": "early",
                    "parameters": [
                        {"name": "q", "in": "querystring", "schema": {"type": "object"}}
                    ],
                    "responses": {"200": {"description": "ok"}},
                }
            },
            "/normal": {
                "get": {
                    "operationId": "normal",
                    "responses": {"200": {"description": "ok"}},
                }
            },
        },
    }
    path = tmp_path / "policy.yaml"
    path.write_text(
        "tools:\n  exclude:\n    operations: ['GET /early', 'GET /normal']\n"
    )
    policy = load_policy_config(str(path))
    behavior = GenerationBehavior(
        tool_grouping="none",
        telemetry="off",
        strict=True,
        runtime_validation="input",
        on_mapping_error=None,
        on_schema_error=None,
    )
    plain = prepare_tools(spec, behavior=behavior, policy=policy)
    traced = prepare_tools(spec, behavior=behavior, policy=policy, trace=True)
    assert plain.public_tools == traced.public_tools == []
    assert [row["status"] for row in traced.trace] == [
        "excluded_before_mapping",
        "mapped_then_excluded",
    ]
    assert all(row["decisions"] for row in traced.trace)


def test_preview_does_not_generate_files_or_launch_process(
    tmp_path, runner, monkeypatch
) -> None:
    import subprocess  # noqa: PLC0415

    from openapi_to_mcp.adapters.generator import Generator  # noqa: PLC0415

    def forbidden(*args, **kwargs):
        raise AssertionError("preview attempted a generation side effect")

    monkeypatch.setattr(Generator, "__init__", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    source = tmp_path / "input.json"
    source.write_text(
        json.dumps(
            {
                "openapi": "3.0.0",
                "info": {"title": "test", "version": "1"},
                "paths": {
                    "/": {
                        "get": {
                            "summary": "café",
                            "responses": {"200": {"description": "ok"}},
                        }
                    }
                },
            }
        )
    )
    result = runner.invoke(cli, ["preview", "-o", str(source), "--format", "json"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert "café" in result.stdout
    expected = len(
        json.dumps(
            report["tools"],
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    )
    assert report["catalog"]["total_bytes"] == expected
    assert not list(workspace.iterdir())


def test_default_preview_equals_generated_catalog_and_exact_threshold(
    tmp_path, runner
) -> None:
    args = ["-o", "tests/resources/test_openapi.yaml"]
    output = tmp_path / "generated"
    generated = runner.invoke(cli, ["generate", *args, "-d", str(output)])
    assert generated.exit_code == 0, generated.output
    content = (output / "src/runtime/generated.ts").read_text()
    tools = json.loads(
        re.search(
            r"export const tools = (\[.*?\]) as Tool\[\];", content, re.DOTALL
        ).group(1)
    )
    preview = runner.invoke(cli, ["preview", *args, "--format", "json"])
    report = json.loads(preview.stdout)
    assert report["tools"] == tools
    size = report["catalog"]["total_bytes"]
    equal = runner.invoke(
        cli, ["preview", *args, "--format", "json", "--max-catalog-bytes", str(size)]
    )
    over = runner.invoke(
        cli,
        ["preview", *args, "--format", "json", "--max-catalog-bytes", str(size - 1)],
    )
    assert equal.exit_code == 0
    assert over.exit_code == 2
    assert json.loads(over.stdout)["tools"] == tools


def test_text_preview_explains_policy_and_grouping_without_override_values(
    tmp_path, runner, monkeypatch
) -> None:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Test", "version": "1"},
        "paths": {
            "/a": {
                "get": {
                    "operationId": "alpha",
                    "tags": ["Pets"],
                    "responses": {"200": {"description": "ok"}},
                }
            },
            "/b": {
                "get": {
                    "operationId": "beta",
                    "tags": ["Cats"],
                    "responses": {"200": {"description": "ok"}},
                }
            },
            "/c": {
                "get": {
                    "operationId": "gamma",
                    "responses": {"200": {"description": "ok"}},
                }
            },
            "/d": {
                "get": {
                    "operationId": "delta",
                    "responses": {"200": {"description": "ok"}},
                }
            },
        },
    }
    source = tmp_path / "spec.json"
    source.write_text(json.dumps(spec))
    policy = tmp_path / "policy.yaml"
    policy.write_text(
        yaml.safe_dump(
            {
                "generate": {"tool_grouping": "tag-prefix"},
                "tools": {
                    "include": {"names": ["alpha", "beta", "gamma"]},
                    "exclude": {"operations": ["GET /c"]},
                    "rename": {"operations": {"GET /a": "safe\nname"}},
                    "descriptions": {
                        "names": {"safe\nname": "secret-description-value"}
                    },
                },
                "auth": {
                    "operations": {
                        "GET /a": {
                            "security": [{"secret-scheme": []}],
                            "security_schemes": {
                                "secret-scheme": {
                                    "type": "apiKey",
                                    "in": "header",
                                    "name": "secret-header-value",
                                }
                            },
                        }
                    }
                },
            }
        )
    )
    monkeypatch.setenv("AUTH_SECRET_SCHEME_API_KEY", "secret-env-value")
    result = runner.invoke(cli, ["preview", "-o", str(source), "--config", str(policy)])
    assert result.exit_code == 0, result.output
    output = result.stdout
    assert 'include name "alpha"' in output
    assert 'rename by operation "GET /a"' in output
    assert 'description override by renamed name "safe\\nname"' in output
    assert 'auth override by operation "GET /a"' in output
    assert "grouping suppressed by policy rename" in output
    assert 'group prefix "cats"' in output
    assert 'include name "gamma"' in output
    assert 'exclude operation "GET /c"' in output
    assert "no include selector matched" in output
    assert '"alpha" -> "safe\\nname"' in output
    assert "safe\nname" not in output
    assert all(
        secret not in result.output
        for secret in (
            "secret-description-value",
            "secret-header-value",
            "secret-env-value",
        )
    )


def test_text_and_json_preserve_each_skipped_operation_source(tmp_path, runner) -> None:
    unsupported = {
        "name": "filter",
        "in": "querystring",
        "content": {"application/json": {"schema": {"type": "object"}}},
    }
    operation = {
        "parameters": [unsupported],
        "responses": {"200": {"description": "ok"}},
    }
    spec = {
        "openapi": "3.2.1",
        "info": {"title": "Test", "version": "1"},
        "paths": {
            "/x": {
                "get": operation,
                "post": operation,
                "additionalOperations": {
                    "Copy": {"responses": {"200": {"description": "ok"}}},
                    "copy": {"responses": {"200": {"description": "ok"}}},
                },
            }
        },
    }
    source = tmp_path / "spec.json"
    source.write_text(json.dumps(spec))
    args = ["preview", "-o", str(source), "--no-strict"]
    text_result = runner.invoke(cli, args)
    json_result = runner.invoke(cli, [*args, "--format", "json"])
    assert text_result.exit_code == json_result.exit_code == 0, text_result.output
    report = json.loads(json_result.stdout)
    rows = report["operations"]
    assert [row["method"] for row in rows] == ["GET", "POST", "COPY", "COPY"]
    assert all(row["status"] == "skipped" for row in rows)
    lines = [
        line.strip()
        for line in text_result.stdout.splitlines()
        if line.strip().startswith("mapping skipped:")
    ]
    assert len(lines) == 4
    locations = [".get", ".post", ".Copy", ".copy"]
    assert all(
        location in line for location, line in zip(locations, lines, strict=True)
    )
    for line, row, location in zip(lines, rows, locations, strict=True):
        assert row.get("skip_reason") is not None
        assert (
            line
            == f"mapping skipped: {json.dumps(row['skip_reason'], ensure_ascii=True)}"
        )
        assert row["source_location"].endswith(location)
