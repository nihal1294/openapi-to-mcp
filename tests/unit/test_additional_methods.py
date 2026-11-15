"""Executable OpenAPI 3.2 method compatibility."""

import pytest

from openapi_to_mcp.common import MappingError
from openapi_to_mcp.doctor import DoctorAnalyzer
from openapi_to_mcp.mapping import Mapper


def test_query_and_additional_methods_are_mapped() -> None:
    spec = {
        "openapi": "3.2.1",
        "paths": {
            "/items": {
                "query": {"operationId": "queryItems", "responses": {"200": {}}},
                "additionalOperations": {
                    "COPY": {"operationId": "copyItems", "responses": {"200": {}}},
                    "PROPFIND": {"operationId": "findItems", "responses": {"200": {}}},
                },
            }
        },
    }
    tools = Mapper(spec).map_tools()
    assert [(tool["name"], tool["_original_method"]) for tool in tools] == [
        ("queryItems", "QUERY"),
        ("copyItems", "COPY"),
        ("findItems", "PROPFIND"),
    ]


@pytest.mark.parametrize(
    ("method", "reason"),
    [
        ("GET", "reserved"),
        ("QUERY", "reserved"),
        ("CONNECT", "tunnelling"),
        ("Copy", "uppercase"),
        ("copy", "uppercase"),
        ("BAD METHOD", "valid ASCII"),
        ("", "valid ASCII"),
        ("MÉTODO", "valid ASCII"),
    ],
)
def test_rejected_additional_methods_report_location_and_skip(
    method: str, reason: str
) -> None:

    spec = {
        "openapi": "3.2.1",
        "paths": {"/x": {"additionalOperations": {method: {"responses": {"200": {}}}}}},
    }
    with pytest.raises(MappingError, match=reason):
        Mapper(spec).map_tools()
    mapper = Mapper(spec, strict=False)
    assert mapper.map_tools() == []
    skipped = mapper.get_report()["skipped_operations"][0]
    assert reason in skipped["reason"]
    issues = DoctorAnalyzer(spec).analyze("inline").issues
    assert any(
        issue.code == "unsupported_openapi_construct"
        and issue.location == f"paths./x.additionalOperations.{method}"
        for issue in issues
    )


def test_additional_method_policy_selection_and_renaming(tmp_path) -> None:
    from openapi_to_mcp.policy import apply_policy  # noqa: PLC0415
    from openapi_to_mcp.policy.models import PolicyConfig, SelectorSet  # noqa: PLC0415

    spec = {
        "openapi": "3.2.1",
        "paths": {
            "/a-b": {"additionalOperations": {"CONNECT": {"responses": {"200": {}}}}},
            "/a_b": {"additionalOperations": {"COPY": {"responses": {"200": {}}}}},
            "/a.b": {"additionalOperations": {"COPY": {"responses": {"200": {}}}}},
        },
    }
    policy = PolicyConfig(
        source_path=tmp_path / "policy.yaml",
        include=SelectorSet(names=frozenset({"copy_a_b_2"})),
        rename_operations={"COPY /a.b": "selectedCopy"},
    )
    mapper = Mapper(spec, strict=False, policy_config=policy)
    tools = mapper.map_tools()
    assert [tool["name"] for tool in tools] == ["copy_a_b", "copy_a_b_2"]
    assert [tool["name"] for tool in apply_policy(tools, policy)] == ["selectedCopy"]
    assert mapper.get_report()["skipped_operations"] == []


@pytest.mark.parametrize("method", ["QUERY", "COPY", "PROPFIND"])
def test_additional_methods_do_not_gain_safe_method_controls(
    tmp_path, method: str
) -> None:
    from openapi_to_mcp.common.exceptions import PolicyConfigError  # noqa: PLC0415
    from openapi_to_mcp.policy import apply_policy  # noqa: PLC0415
    from openapi_to_mcp.policy.models import ExecutionOverride, PolicyConfig  # noqa: PLC0415

    operation = {"responses": {"200": {}}}
    item = (
        {"query": operation}
        if method == "QUERY"
        else {"additionalOperations": {method: operation}}
    )
    tools = Mapper({"openapi": "3.2.1", "paths": {"/x": item}}).map_tools()
    policy = PolicyConfig(
        source_path=tmp_path / "policy.yaml",
        execution_operations={
            f"{method} /x": ExecutionOverride(cache_ttl_ms=1000, retry_max_retries=1)
        },
    )
    with pytest.raises(PolicyConfigError, match="safe HTTP method"):
        apply_policy(tools, policy)
