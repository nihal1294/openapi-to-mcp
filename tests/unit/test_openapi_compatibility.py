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
from openapi_to_mcp.policy.models import PolicyConfig, SelectorSet

if TYPE_CHECKING:
    from click.testing import CliRunner


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


def test_querystring_parameters_follow_effective_override_and_local_references() -> (
    None
):
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
                "parameters": [{"$ref": "#/components/parameters/wholeQuery"}],
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
                    "parameters": [{"$ref": "#/components/parameters/wholeQuery"}],
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
