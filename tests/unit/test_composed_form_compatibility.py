"""The bounded allOf form layout retains its original validation schema."""

from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import yaml

from openapi_to_mcp.common import MappingError
from openapi_to_mcp.common.form_media import FormMediaError, normalize_form_media
from openapi_to_mcp.doctor import DoctorAnalyzer
from openapi_to_mcp.mapping import Mapper
from openapi_to_mcp.policy.models import PolicyConfig, SelectorSet

if TYPE_CHECKING:
    from collections.abc import Callable

FIXTURE = Path(__file__).parents[1] / "resources/form_compatibility/composed.yaml"


def fixture() -> dict:
    return yaml.safe_load(FIXTURE.read_text())


def test_fixture_accepts_composed_fields_without_mutating_source() -> None:
    spec = fixture()
    original = deepcopy(spec)
    media = spec["paths"]["/send"]["post"]["requestBody"]["content"][
        "application/x-www-form-urlencoded"
    ]
    result = normalize_form_media(spec, media)
    assert list(result["fields"]) == ["name", "count"]
    assert result["fields"]["name"]["mode"] == "style"
    assert result["fields"]["count"]["kind"] == "integer"
    tools = Mapper(spec, on_mapping_error="skip").map_tools()
    assert {tool["name"] for tool in tools} == {"sendComposed", "ordinaryNeighbor"}
    send = next(tool for tool in tools if tool["name"] == "sendComposed")
    assert "allOf" in str(send["inputSchema"])
    assert spec == original


@pytest.mark.parametrize(
    "branch",
    [
        {"type": "object", "properties": {"name": {"type": "string"}}},
        {"type": "object", "properties": {}, "additionalProperties": False},
        {"type": "object", "properties": {}, "required": ["name"]},
        {"type": "object", "properties": {}, "minProperties": 1},
        {"properties": {}},
        {"type": "object", "allOf": [], "properties": {}},
        {"type": "object", "properties": {"x": {"type": "array"}}},
        {"type": "object", "properties": {"x": {"type": "string", "minLength": True}}},
        {
            "type": "object",
            "properties": {"x": {"type": "integer", "minimum": float("inf")}},
        },
        {
            "type": "object",
            "properties": {"x": {"type": "boolean", "enum": [True, True]}},
        },
        {"$ref": "#/components/schemas/NameChain", "description": "sibling"},
        {"$ref": "https://example.com/schema"},
    ],
)
def test_rejects_unsupported_branches(branch: dict) -> None:
    spec = fixture()
    spec["components"]["schemas"]["Form"]["allOf"].append(branch)
    with pytest.raises(FormMediaError):
        normalize_form_media(spec, {"schema": {"$ref": "#/components/schemas/Form"}})


def test_diagnostics_and_original_assertions() -> None:
    spec = fixture()
    with pytest.raises(MappingError, match=r"paths\./neighbor\.post\.requestBody"):
        Mapper(spec).map_tools()
    mapper = Mapper(spec, on_mapping_error="skip")
    tools = mapper.map_tools()
    skipped = mapper.get_report()["skipped_operations"]
    assert [(entry["method"], entry["path"]) for entry in skipped] == [
        ("POST", "/neighbor")
    ]
    assert "paths./neighbor.post.requestBody" in skipped[0]["reason"]
    issues = DoctorAnalyzer(spec).analyze("inline").issues
    assert [
        (i.code, i.location)
        for i in issues
        if i.code == "unsupported_openapi_construct"
    ] == [("unsupported_openapi_construct", "paths./neighbor.post.requestBody")]
    schema = next(tool for tool in tools if tool["name"] == "sendComposed")[
        "inputSchema"
    ]
    for name in ("whole", "requestBody"):
        branches = schema["properties"][name]["allOf"]
        assert branches[0]["properties"]["name"] == {
            "type": "string",
            "minLength": 2,
            "maxLength": 12,
        }
        assert branches[0]["required"] == ["name"]
        assert branches[1]["properties"]["count"] == {
            "type": "integer",
            "minimum": 1,
            "maximum": 9,
        }
        assert branches[1]["required"] == ["count"]
    policy = PolicyConfig(
        source_path=Path("policy.yaml"),
        exclude=SelectorSet(operations=frozenset({"POST /neighbor"})),
    )
    assert {
        tool["name"] for tool in Mapper(spec, policy_config=policy).map_tools()
    } == {"sendComposed", "ordinaryNeighbor"}


def test_escaped_field_ref_and_prototype_names() -> None:
    spec = fixture()
    schemas = spec["components"]["schemas"]
    schemas["Name"]["properties"] = {
        "__proto__": {"$ref": "#/components/schemas/Fields/properties/a~1~0"},
        "constructor": {"type": "boolean"},
    }
    schemas["Name"]["required"] = ["__proto__"]
    schemas["Fields"] = {"type": "object", "properties": {"a/~": {"type": "string"}}}
    result = normalize_form_media(
        spec, {"schema": {"$ref": "#/components/schemas/Form"}}
    )
    assert list(result["fields"]) == ["__proto__", "constructor", "count"]
    assert result["fields"]["__proto__"]["kind"] == "string"


@pytest.mark.parametrize(
    "change",
    [
        lambda root: root.update(properties={}),
        lambda root: root.update(required=[]),
        lambda root: root.update(additionalProperties=True),
        lambda root: root.update(title=3),
        lambda root: root.update(allOf=[]),
        lambda root: root.update(allOf=[{"$ref": "#/components/schemas/Form"}]),
        lambda root: root.update(allOf=[{"$ref": "#/components/schemas/Missing"}]),
        lambda root: root.update(allOf=[{"$ref": "#/components/schemas/Cycle"}]),
    ],
)
def test_rejects_invalid_roots_and_references(change: Callable[[dict], None]) -> None:
    spec = fixture()
    spec["components"]["schemas"]["Cycle"] = {"$ref": "#/components/schemas/Cycle"}
    change(spec["components"]["schemas"]["Form"])
    with pytest.raises(FormMediaError):
        normalize_form_media(spec, {"schema": {"$ref": "#/components/schemas/Form"}})


@pytest.mark.parametrize(
    "field",
    [
        {"type": "string", "maxLength": -1},
        {"type": "string", "pattern": 3},
        {"type": "number", "minimum": True},
        {"type": "number", "multipleOf": 0},
        {"type": "integer", "default": 1.5},
        {"type": "integer", "enum": [1, 1.0]},
        {"type": "string", "examples": [1]},
        {"type": "boolean", "example": 1},
        {"type": "string", "deprecated": "yes"},
        {"type": "string", "format": "email"},
        {"type": ["string", "null"]},
        {"type": "string", "nullable": False},
        {"type": "number", "exclusiveMinimum": 1},
        {"const": "x"},
        {"$ref": "#/components/schemas/Name", "title": "sibling"},
    ],
)
def test_rejects_invalid_field_schema(field: dict) -> None:
    spec = fixture()
    spec["components"]["schemas"]["Name"]["properties"]["name"] = field
    with pytest.raises(FormMediaError):
        normalize_form_media(spec, {"schema": {"$ref": "#/components/schemas/Form"}})


@pytest.mark.parametrize("version", ["3.0.3", "3.1.2", "3.2.0"])
def test_scalar_assertions_and_annotations_are_preserved(version: str) -> None:
    spec = fixture()
    spec["openapi"] = version
    name = spec["components"]["schemas"]["Name"]["properties"]["name"]
    name.update(
        {
            "enum": ["ab", "cd"],
            "const": "ab",
            "pattern": "^[a-z]+$",
            "default": "ab",
            "example": "cd",
            "examples": ["ab"],
            "description": "name",
            "readOnly": False,
        }
    )
    count = spec["components"]["schemas"]["Form"]["allOf"][1]["properties"]["count"]
    count.update({"multipleOf": 1, "enum": [1, 2.0], "const": 1, "default": 2.0})
    if version != "3.2.0":
        spec["paths"]["/send"]["post"].pop("parameters")
    original = deepcopy(spec)
    tool = next(
        tool
        for tool in Mapper(spec, on_mapping_error="skip").map_tools()
        if tool["name"] == "sendComposed"
    )
    branches = tool["inputSchema"]["properties"]["requestBody"]["allOf"]
    converted_name = branches[0]["properties"]["name"]
    converted_count = branches[1]["properties"]["count"]
    for key in (
        "enum",
        "const",
        "pattern",
        "default",
        "description",
        "readOnly",
        "minLength",
        "maxLength",
    ):
        assert converted_name[key] == name[key]
    assert converted_name["examples"] == ["cd"]
    for key in ("minimum", "maximum", "multipleOf", "enum", "const", "default"):
        assert converted_count[key] == count[key]
    assert spec == original
