"""Compatibility coverage for OpenAPI constructs that cannot be generated."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from openapi_to_mcp.cli import cli
from openapi_to_mcp.common import MappingError
from openapi_to_mcp.doctor import DoctorAnalyzer
from openapi_to_mcp.mapping import Mapper
from openapi_to_mcp.policy import apply_policy
from openapi_to_mcp.policy.models import PolicyConfig, SelectorSet

if TYPE_CHECKING:
    from typing import Any

    from click.testing import CliRunner


@pytest.fixture
def encoded_querystring_spec() -> dict[str, Any]:
    return {
        "openapi": "3.2.1",
        "info": {"title": "Encoded parameter reference", "version": "1.0.0"},
        "servers": [{"url": "https://example.com"}],
        "components": {
            "parameters": {
                "wholeQuery": {
                    "name": "filter",
                    "in": "querystring",
                    "content": {"application/json": {"schema": {"type": "object"}}},
                }
            }
        },
        "paths": {
            "/ping": {
                "get": {
                    "operationId": "ping",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/search": {
                "get": {
                    "operationId": "search",
                    "parameters": [{"$ref": "#/components/parameters/%77holeQuery"}],
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
    }


def test_doctor_reports_percent_encoded_querystring_reference(
    runner: CliRunner, tmp_path: Path, encoded_querystring_spec: dict[str, Any]
) -> None:
    source = tmp_path / "openapi.json"
    source.write_text(json.dumps(encoded_querystring_spec), encoding="utf-8")

    result = runner.invoke(cli, ["doctor", "-o", str(source), "--format", "json"])

    assert result.exit_code == 3
    issues = json.loads(result.output[result.output.index("{\n") :])["issues"]
    findings = [
        issue for issue in issues if issue["code"] == "unsupported_openapi_construct"
    ]
    assert [issue["location"] for issue in findings] == [
        "components.parameters.wholeQuery.in"
    ]
    assert "in: querystring" in findings[0]["message"]


def test_generate_strict_rejects_percent_encoded_querystring_reference(
    runner: CliRunner, tmp_path: Path, encoded_querystring_spec: dict[str, Any]
) -> None:
    source = tmp_path / "openapi.json"
    source.write_text(json.dumps(encoded_querystring_spec), encoding="utf-8")
    destination = tmp_path / "generated"

    result = runner.invoke(cli, ["generate", "-o", str(source), "-d", str(destination)])

    assert result.exit_code == 1
    assert "GET /search" in result.output
    assert "components.parameters.wholeQuery.in" in result.output
    assert not destination.exists()


def test_generate_skip_accounts_for_percent_encoded_querystring_reference(
    runner: CliRunner, tmp_path: Path, encoded_querystring_spec: dict[str, Any]
) -> None:
    source = tmp_path / "openapi.json"
    source.write_text(json.dumps(encoded_querystring_spec), encoding="utf-8")
    destination = tmp_path / "generated"

    result = runner.invoke(
        cli,
        [
            "generate",
            "-o",
            str(source),
            "-d",
            str(destination),
            "--on-mapping-error",
            "skip",
        ],
    )

    assert result.exit_code == 0
    report = json.loads((destination / "generation_report.json").read_text())
    assert report["mapped_tools"] == 1
    assert len(report["skipped_operations"]) == 1
    skipped = report["skipped_operations"][0]
    assert (skipped["method"], skipped["path"]) == ("GET", "/search")
    assert "in: querystring" in skipped["reason"]
    assert "components.parameters.wholeQuery.in" in skipped["reason"]


@pytest.mark.parametrize(
    ("parameter_key", "reference"),
    [
        ("wholeQuery", "#/components%2Fparameters%2FwholeQuery"),
        ("café", "#/components/parameters/caf%C3%A9"),
        ("query/~", "#/components/parameters/query%7E1%7E0"),
        ("%77holeQuery", "#/components/parameters/%2577holeQuery"),
    ],
)
def test_querystring_reference_decodes_fragment_once_before_pointer_tokens(
    encoded_querystring_spec: dict[str, Any], parameter_key: str, reference: str
) -> None:
    parameters = encoded_querystring_spec["components"]["parameters"]
    parameters[parameter_key] = parameters.pop("wholeQuery")
    encoded_querystring_spec["paths"]["/search"]["get"]["parameters"] = [
        {"$ref": reference}
    ]

    report = DoctorAnalyzer(encoded_querystring_spec).analyze("inline")

    assert [
        issue.location
        for issue in report.issues
        if issue.code == "unsupported_openapi_construct"
    ] == [f"components.parameters.{parameter_key}.in"]


def test_mapper_rejects_additional_operation_in_strict_mode() -> None:
    """Additional operations must not silently disappear during generation."""
    spec = {
        "openapi": "3.2.1",
        "info": {"title": "Additional operations", "version": "1.0.0"},
        "paths": {
            "/ping": {
                "get": {"operationId": "ping", "responses": {"200": {}}},
                "additionalOperations": {
                    "COPY": {
                        "operationId": "copyPing",
                        "responses": {"200": {}},
                    }
                },
            }
        },
    }

    with pytest.raises(MappingError, match=r"COPY /ping"):
        Mapper(spec).map_tools()


def test_mapper_skips_additional_operation_without_consuming_tool_suffix() -> None:
    """Skip mode preserves supported siblings and leaves their names available."""
    spec = {
        "openapi": "3.2.1",
        "info": {"title": "Additional operations", "version": "1.0.0"},
        "paths": {
            "/ping": {
                "get": {"operationId": "shared", "responses": {"200": {}}},
                "additionalOperations": {
                    "COPY": {
                        "operationId": "shared",
                        "responses": {"200": {}},
                    }
                },
            },
            "/pong": {"get": {"operationId": "shared", "responses": {"200": {}}}},
        },
    }

    mapper = Mapper(spec, strict=False)

    assert [tool["name"] for tool in mapper.map_tools()] == ["shared", "shared_2"]
    assert mapper.get_report()["skipped_operations"] == [
        {
            "method": "COPY",
            "path": "/ping",
            "reason": "unsupported OpenAPI construct `additionalOperations` at "
            "`paths./ping.additionalOperations.COPY`; Additional operations are "
            "diagnostic-only. Use a supported fixed HTTP operation before "
            "generating an MCP server.",
        }
    ]


def test_explicit_mapping_skip_overrides_strict_for_query_operation() -> None:
    """Explicit skip mode permits partial generation even when strict is enabled."""
    spec = {
        "openapi": "3.2.1",
        "info": {"title": "Query", "version": "1.0.0"},
        "paths": {
            "/items": {
                "get": {"operationId": "listItems", "responses": {"200": {}}},
                "query": {
                    "operationId": "queryItems",
                    "responses": {"200": {}},
                },
            }
        },
    }

    mapper = Mapper(spec, strict=True, on_mapping_error="skip")

    assert [tool["name"] for tool in mapper.map_tools()] == ["listItems"]
    assert mapper.get_report()["skipped_operations"][0]["method"] == "QUERY"


def test_mapper_preserves_suffix_name_policy_selection_for_supported_operations() -> (
    None
):
    """Supported operations retain legacy post-mapping name allocation behavior."""
    spec = {
        "openapi": "3.0.4",
        "info": {"title": "Suffix selection", "version": "1.0.0"},
        "paths": {
            "/a-b": {"get": {"responses": {"200": {}}}},
            "/a_b": {"get": {"responses": {"200": {}}}},
        },
    }
    policy = PolicyConfig(
        source_path=Path("mcpgen.yaml"),
        include=SelectorSet(names=frozenset({"get_a_b_2"})),
    )

    mapper = Mapper(spec, strict=False, policy_config=policy)
    tools = mapper.map_tools()

    assert [tool["name"] for tool in tools] == ["get_a_b", "get_a_b_2"]
    assert [tool["name"] for tool in apply_policy(tools, policy)] == ["get_a_b_2"]


def test_doctor_config_honors_non_strict_suffixed_name_selection(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Doctor and non-strict generation agree on allocated policy names."""
    spec = {
        "openapi": "3.0.4",
        "info": {"title": "Suffix doctor selection", "version": "1.0.0"},
        "servers": [{"url": "https://example.com"}],
        "paths": {
            "/a-b": {"get": {"responses": {"200": {"description": "OK"}}}},
            "/a_b": {"get": {"responses": {"200": {"description": "OK"}}}},
        },
    }
    source = tmp_path / "openapi.json"
    source.write_text(json.dumps(spec), encoding="utf-8")
    config = tmp_path / "mcpgen.yaml"
    config.write_text("tools:\n  include:\n    names: [get_a_b_2]\n", encoding="utf-8")

    doctor_result = runner.invoke(
        cli,
        ["doctor", "-o", str(source), "--config", str(config), "--format", "json"],
    )
    generated = tmp_path / "generated"
    generate_result = runner.invoke(
        cli,
        [
            "generate",
            "-o",
            str(source),
            "--config",
            str(config),
            "--no-strict",
            "-d",
            str(generated),
        ],
    )

    assert doctor_result.exit_code == 2
    assert "no_selected_operations" not in doctor_result.output
    assert "tool_name_collision" not in doctor_result.output
    assert generate_result.exit_code == 0
    report = json.loads((generated / "generation_report.json").read_text())
    assert report["mapped_tools"] == 1


@pytest.mark.parametrize(
    ("selected_name", "selected_path", "unsupported_selected"),
    [("get_a_b", "/a_b", True), ("get_a_b_2", "/a.b", False)],
)
def test_doctor_name_selection_does_not_reserve_unsupported_operation_names(
    runner: CliRunner,
    tmp_path: Path,
    selected_name: str,
    selected_path: str,
    *,
    unsupported_selected: bool,
) -> None:
    """Skipped querystring operations do not displace compatible source identities."""
    spec = {
        "openapi": "3.2.1",
        "info": {"title": "Querystring sibling selection", "version": "1.0.0"},
        "servers": [{"url": "https://example.com"}],
        "components": {
            "securitySchemes": {"digestAuth": {"type": "http", "scheme": "digest"}}
        },
        "paths": {
            "/a-b": {
                "get": {
                    "parameters": [
                        {
                            "name": "filter",
                            "in": "querystring",
                            "content": {
                                "application/json": {"schema": {"type": "object"}}
                            },
                        }
                    ],
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/a_b": {
                "get": {
                    "security": [{"digestAuth": []}],
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/a.b": {
                "get": {
                    "security": [{"digestAuth": []}],
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
    }
    policy = PolicyConfig(
        source_path=Path("mcpgen.yaml"),
        include=SelectorSet(names=frozenset({selected_name})),
    )
    mapper = Mapper(spec, strict=False, policy_config=policy)
    tools = apply_policy(mapper.map_tools(), policy)
    assert [(tool["name"], tool["_original_path"]) for tool in tools] == [
        (selected_name, selected_path)
    ]

    source = tmp_path / "openapi.json"
    source.write_text(json.dumps(spec), encoding="utf-8")
    config = tmp_path / "mcpgen.yaml"
    config.write_text(
        f"tools:\n  include:\n    names: [{selected_name}]\n", encoding="utf-8"
    )
    result = runner.invoke(
        cli,
        ["doctor", "-o", str(source), "--config", str(config), "--format", "json"],
    )

    assert result.exit_code == 3
    issues = json.loads(result.output[result.output.index("{\n") :])["issues"]
    assert [
        issue["location"]
        for issue in issues
        if issue["code"] == "unsupported_http_auth"
    ] == [f"paths.{selected_path}.get.security"]
    codes = {issue["code"] for issue in issues}
    assert ("unsupported_openapi_construct" in codes) is unsupported_selected
    assert ("tool_name_collision" in codes) is unsupported_selected
    assert "no_selected_operations" not in codes


@pytest.mark.parametrize(
    "parameter_ref",
    ["#/components/parameters/wholeQuery", "#/components/parameters/%77holeQuery"],
)
def test_querystring_parameters_follow_effective_override_and_local_references(
    parameter_ref: str,
) -> None:
    """A same-identity operation parameter replaces its inherited source."""
    spec = {
        "openapi": "3.2.1",
        "info": {"title": "Query string", "version": "1.0.0"},
        "components": {
            "parameters": {
                "wholeQuery": {
                    "name": "filter",
                    "in": "querystring",
                    "content": {"application/json": {"schema": {"type": "object"}}},
                },
                "unused": {"name": "unused", "in": "querystring"},
            }
        },
        "paths": {
            "/items": {
                "parameters": [{"$ref": parameter_ref}],
                "get": {
                    "operationId": "listItems",
                    "parameters": [
                        {
                            "name": "filter",
                            "in": "querystring",
                            "content": {
                                "application/json": {"schema": {"type": "object"}}
                            },
                        }
                    ],
                    "responses": {"200": {}},
                },
            },
            "/search": {
                "get": {
                    "operationId": "searchItems",
                    "parameters": [{"$ref": parameter_ref}],
                    "responses": {"200": {}},
                }
            },
        },
    }

    report = DoctorAnalyzer(spec).analyze("inline")
    findings = [
        issue
        for issue in report.issues
        if issue.code == "unsupported_openapi_construct"
    ]

    assert [(issue.location, issue.message) for issue in findings] == [
        (
            "paths./items.get.parameters[0].in",
            "OpenAPI `in: querystring` cannot be faithfully generated.",
        ),
        (
            "components.parameters.wholeQuery.in",
            "OpenAPI `in: querystring` cannot be faithfully generated.",
        ),
    ]


def test_policy_excluded_operations_do_not_emit_openapi_compatibility_findings() -> (
    None
):
    """Compatibility findings honor the same operation selectors as generation."""
    spec = {
        "openapi": "3.2.1",
        "info": {"title": "Policy", "version": "1.0.0"},
        "paths": {
            "/ping": {
                "get": {"operationId": "ping", "responses": {"200": {}}},
                "additionalOperations": {
                    "COPY": {
                        "operationId": "copyPing",
                        "responses": {"200": {}},
                    }
                },
            }
        },
    }
    policy = PolicyConfig(
        source_path=Path("mcpgen.yaml"),
        exclude=SelectorSet(operations=frozenset({"COPY /ping"})),
    )

    assert Mapper(spec, policy_config=policy).map_tools()[0]["name"] == "ping"
    report = DoctorAnalyzer(spec, policy).analyze("inline")
    assert not [
        issue
        for issue in report.issues
        if issue.code == "unsupported_openapi_construct"
    ]


def test_additional_only_document_has_compatibility_error_not_no_operations() -> None:
    """Diagnostic inventory recognizes additional-only OpenAPI 3.2 documents."""
    spec = {
        "openapi": "3.2.1",
        "info": {"title": "Additional only", "version": "1.0.0"},
        "paths": {
            "/copy": {"additionalOperations": {"COPY": {"responses": {"200": {}}}}}
        },
    }

    codes = {issue.code for issue in DoctorAnalyzer(spec).analyze("inline").issues}
    assert "unsupported_openapi_construct" in codes
    assert "no_http_operations" not in codes


def test_generate_strict_failure_writes_no_partial_project_and_skip_reports_copy(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Generation fails atomically by default and reports the skipped COPY explicitly."""
    spec = {
        "openapi": "3.2.1",
        "info": {"title": "Generation", "version": "1.0.0"},
        "paths": {
            "/ping": {
                "get": {"operationId": "ping", "responses": {"200": {}}},
                "additionalOperations": {
                    "COPY": {
                        "operationId": "copyPing",
                        "responses": {"200": {}},
                    }
                },
            }
        },
    }
    source = tmp_path / "openapi.json"
    source.write_text(json.dumps(spec), encoding="utf-8")
    strict_output = tmp_path / "strict-output"

    strict_result = runner.invoke(
        cli,
        ["generate", "-o", str(source), "-d", str(strict_output)],
    )

    assert strict_result.exit_code == 1
    assert "COPY /ping" in strict_result.output
    assert not strict_output.exists()

    skipped_output = tmp_path / "skipped-output"
    skipped_result = runner.invoke(
        cli,
        [
            "generate",
            "-o",
            str(source),
            "-d",
            str(skipped_output),
            "--on-mapping-error",
            "skip",
        ],
    )

    assert skipped_result.exit_code == 0
    report = json.loads((skipped_output / "generation_report.json").read_text())
    assert report["mapped_tools"] == 1
    assert report["skipped_operations"] == [
        {
            "method": "COPY",
            "path": "/ping",
            "reason": "unsupported OpenAPI construct `additionalOperations` at "
            "`paths./ping.additionalOperations.COPY`; Additional operations are "
            "diagnostic-only. Use a supported fixed HTTP operation before "
            "generating an MCP server.",
        }
    ]


def test_doctor_config_excludes_unselected_additional_operation(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Doctor uses explicit policy selection for OpenAPI compatibility findings."""
    spec = {
        "openapi": "3.2.1",
        "info": {"title": "Doctor policy", "version": "1.0.0"},
        "servers": [{"url": "https://example.com"}],
        "paths": {
            "/ping": {
                "get": {"operationId": "ping", "responses": {"200": {}}},
                "additionalOperations": {
                    "COPY": {
                        "operationId": "copyPing",
                        "responses": {"200": {}},
                    }
                },
            }
        },
    }
    source = tmp_path / "openapi.json"
    source.write_text(json.dumps(spec), encoding="utf-8")
    config = tmp_path / "mcpgen.yaml"
    config.write_text(
        "tools:\n  exclude:\n    operations: [COPY /ping]\n", encoding="utf-8"
    )

    result = runner.invoke(
        cli,
        ["doctor", "-o", str(source), "--config", str(config), "--format", "json"],
    )

    assert result.exit_code == 0
    assert "unsupported_openapi_construct" not in result.output


def test_doctor_config_execution_override_does_not_replace_copy_diagnostic(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Compatibility reporting applies selectors without validating execution policy."""
    spec = {
        "openapi": "3.2.1",
        "info": {"title": "Doctor execution policy", "version": "1.0.0"},
        "servers": [{"url": "https://example.com"}],
        "paths": {
            "/ping": {
                "additionalOperations": {
                    "COPY": {
                        "operationId": "copyPing",
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            }
        },
    }
    source = tmp_path / "openapi.json"
    source.write_text(json.dumps(spec), encoding="utf-8")
    config = tmp_path / "mcpgen.yaml"
    config.write_text(
        "execution:\n  operations:\n    COPY /ping:\n      cache_ttl_ms: 60\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        cli,
        ["doctor", "-o", str(source), "--config", str(config), "--format", "json"],
    )

    assert result.exit_code == 3
    assert "unsupported_openapi_construct" in result.output
    assert "require a safe HTTP method" not in result.output


def test_doctor_config_excludes_unsupported_swagger_sibling(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Doctor applies explicit selection before Swagger compatibility checks."""
    spec = {
        "swagger": "2.0",
        "info": {"title": "Doctor Swagger policy", "version": "1.0.0"},
        "host": "api.example.com",
        "paths": {
            "/good": {
                "get": {
                    "operationId": "getGood",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/bad": {
                "get": {
                    "operationId": "getBad",
                    "parameters": [
                        {
                            "name": "payload",
                            "in": "body",
                            "schema": {"type": "object"},
                        }
                    ],
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
    }
    source = tmp_path / "swagger.json"
    source.write_text(json.dumps(spec), encoding="utf-8")
    config = tmp_path / "mcpgen.yaml"
    config.write_text(
        "tools:\n  exclude:\n    operations: [GET /bad]\n", encoding="utf-8"
    )

    result = runner.invoke(
        cli,
        ["doctor", "-o", str(source), "--config", str(config), "--format", "json"],
    )

    assert result.exit_code == 0
    assert "unsupported_swagger_construct" not in result.output


def test_doctor_reports_no_selected_operations_but_keeps_global_checks(
    runner: CliRunner, tmp_path: Path
) -> None:
    """A nonempty document filtered to zero operations is not an empty document."""
    spec = {
        "openapi": "3.2.1",
        "info": {"title": "No selected operations", "version": "1.0.0"},
        "paths": {
            "/ping": {
                "get": {
                    "operationId": "ping",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    source = tmp_path / "openapi.json"
    source.write_text(json.dumps(spec), encoding="utf-8")
    config = tmp_path / "mcpgen.yaml"
    config.write_text(
        "tools:\n  exclude:\n    operations: [GET /ping]\n", encoding="utf-8"
    )

    result = runner.invoke(
        cli,
        ["doctor", "-o", str(source), "--config", str(config), "--format", "json"],
    )

    assert result.exit_code == 3
    assert "no_selected_operations" in result.output
    assert "no_http_operations" not in result.output
    assert "missing_base_url" in result.output


def test_doctor_config_filters_operation_security_and_schema_checks(
    runner: CliRunner, tmp_path: Path
) -> None:
    """Excluded operations do not contribute security or union readiness findings."""
    spec = {
        "openapi": "3.2.1",
        "info": {"title": "Doctor operation checks", "version": "1.0.0"},
        "servers": [{"url": "https://example.com"}],
        "paths": {
            "/good": {
                "get": {
                    "operationId": "getGood",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/excluded": {
                "post": {
                    "operationId": "postExcluded",
                    "security": [{"missingAuth": []}],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "oneOf": [
                                        {"type": "object", "properties": {"a": {}}},
                                        {"type": "object", "properties": {"b": {}}},
                                    ]
                                }
                            }
                        }
                    },
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
    }
    source = tmp_path / "openapi.json"
    source.write_text(json.dumps(spec), encoding="utf-8")
    config = tmp_path / "mcpgen.yaml"
    config.write_text(
        "tools:\n  exclude:\n    operations: [POST /excluded]\n", encoding="utf-8"
    )

    result = runner.invoke(
        cli,
        ["doctor", "-o", str(source), "--config", str(config), "--format", "json"],
    )

    assert result.exit_code == 0
    assert "undefined_security_scheme" not in result.output
    assert "risky_union_schema" not in result.output


@pytest.mark.parametrize("version", ["3.0.4", "3.1.2", "3.2.1"])
def test_fixed_get_generation_and_doctor_matrix(
    version: str, runner: CliRunner, tmp_path: Path
) -> None:
    """Supported fixed operations keep their stable 3.x command behavior."""
    spec = {
        "openapi": version,
        "info": {"title": "Version matrix", "version": "1.0.0"},
        "servers": [{"url": "https://example.com"}],
        "paths": {
            "/ping": {
                "get": {
                    "operationId": "ping",
                    "responses": {"200": {"description": "OK"}},
                }
            }
        },
    }
    source = tmp_path / f"openapi-{version}.json"
    source.write_text(json.dumps(spec), encoding="utf-8")

    doctor_result = runner.invoke(cli, ["doctor", "-o", str(source)])
    generate_result = runner.invoke(
        cli,
        ["generate", "-o", str(source), "-d", str(tmp_path / f"output-{version}")],
    )

    assert doctor_result.exit_code == 0
    assert generate_result.exit_code == 0
