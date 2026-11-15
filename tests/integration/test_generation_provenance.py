from __future__ import annotations

import hashlib
import importlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from click.testing import CliRunner

from openapi_to_mcp.adapters.spec_loader import SpecLoader
from openapi_to_mcp.cli import cli
from openapi_to_mcp.commands.generation_models import (
    GenerationBehavior,
    GenerationRequest,
    GenerationSettings,
    ServerIdentity,
    TransportSettings,
)
from openapi_to_mcp.commands.generation_provenance import _digest, build_provenance
from openapi_to_mcp.commands.generation_service import generate_project
from openapi_to_mcp.common.exceptions import GenerationError, SpecLoaderError
from openapi_to_mcp.policy.models import (
    AuthOverride,
    ExecutionOverride,
    PolicyConfig,
    SelectorSet,
    ToolAnnotationOverride,
)

SPEC = """openapi: 3.0.3
info:
  title: Café
  version: '1'
paths:
  /ping:
    get:
      operationId: ping
      responses:
        '200':
          description: OK
"""


def _settings():
    return GenerationSettings(
        ServerIdentity(None, None),
        TransportSettings("stdio", "secret-host", None, "/secret"),
        GenerationBehavior(
            tool_grouping="none",
            telemetry="off",
            strict=True,
            runtime_validation="input",
            on_mapping_error=None,
            on_schema_error=None,
        ),
    )


def _record(policy=None, config=None):
    return build_provenance(
        source_kind="file",
        spec_digest="a" * 64,
        settings=config or _settings(),
        policy=policy,
    )


def test_cli_generate_and_run_opt_in_and_custom_preservation(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "secret-spec.yaml"
    path.write_text(SPEC, encoding="utf-8")
    output = tmp_path / "out"
    runner = CliRunner()
    args = [
        "--openapi-json",
        str(path),
        "--output-dir",
        str(output),
        "--transport",
        "stdio",
    ]
    default = runner.invoke(cli, ["generate", *args])
    assert default.exit_code == 0, default.output
    assert "provenance" not in json.loads(
        (output / "generation_report.json").read_text()
    )
    custom = output / "src/custom/tools.ts"
    custom.write_text("// preserved custom secret\n")
    monkeypatch.setenv("PROVENANCE_SECRET", "env-secret-marker")

    run_module = importlib.import_module("openapi_to_mcp.commands.run")
    monkeypatch.setattr(run_module, "ensure_runtime_tools", lambda: None)
    monkeypatch.setattr(run_module, "_execute_runtime", lambda *_args: None)
    monkeypatch.setattr(run_module, "_prepare_runtime", lambda *_args: {})
    result = runner.invoke(cli, ["run", *args])
    assert result.exit_code == 0, result.output
    assert "provenance" not in json.loads(
        (output / "generation_report.json").read_text()
    )
    result = runner.invoke(cli, ["run", *args, "--provenance"])
    assert result.exit_code == 0, result.output
    first = json.loads((output / "generation_report.json").read_text())["provenance"]
    assert custom.read_text() == "// preserved custom secret\n"
    assert first["spec"]["digest"]["value"] == hashlib.sha256(SPEC.encode()).hexdigest()
    result = runner.invoke(cli, ["generate", *args, "--provenance"])
    assert result.exit_code == 0, result.output
    second = json.loads((output / "generation_report.json").read_text())["provenance"]
    assert first == second
    assert all(
        secret not in json.dumps(first)
        for secret in (str(path), "secret-host", "env-secret-marker", "Café")
    )


def test_policy_projection_scope_and_order() -> None:
    policy = PolicyConfig(
        Path("/secret"),
        include=SelectorSet(frozenset({"b", "a"}), frozenset()),
        rename_operations={"secret-selector": "secret-rename"},
        annotation_names={"a": ToolAnnotationOverride(read_only=True)},
        execution_operations={"b": ExecutionOverride(timeout_ms=10)},
        auth_names={"a": AuthOverride(security=[{"secret": []}])},
        description_names={"a": "secret-description"},
    )
    base = _record(policy)
    digest = base["policy_digest"]["value"]
    assert (
        _record(
            replace(
                policy,
                source_path=Path("/other"),
                auth_names={},
                description_names={"a": "different"},
            )
        )["policy_digest"]["value"]
        == digest
    )
    assert (
        _record(
            replace(policy, include=SelectorSet(frozenset({"a", "b"}), frozenset()))
        )["policy_digest"]["value"]
        == digest
    )
    for changed in (
        replace(policy, include=SelectorSet(frozenset({"c"}))),
        replace(policy, rename_operations={"secret-selector": "other"}),
        replace(
            policy, annotation_names={"a": ToolAnnotationOverride(read_only=False)}
        ),
        replace(policy, execution_operations={"b": ExecutionOverride(timeout_ms=11)}),
        replace(policy, execution_operations={"c": ExecutionOverride(timeout_ms=10)}),
    ):
        assert _record(changed)["policy_digest"]["value"] != digest
    assert (
        _record(None)["policy_digest"]
        != _record(PolicyConfig(Path("empty")))["policy_digest"]
    )
    assert base["policy_projection"]["auth"]
    assert base["policy_projection"]["descriptions"]
    assert "secret" not in json.dumps(base)


def test_resolution_canonicalization_and_invalid_values() -> None:
    explicit = replace(
        _settings(),
        behavior=replace(
            _settings().behavior, on_mapping_error="fail", on_schema_error="fail"
        ),
    )
    assert (
        _record()["config_projection_digest"]
        == _record(config=explicit)["config_projection_digest"]
    )
    assert (
        _record(
            config=replace(explicit, behavior=replace(explicit.behavior, strict=False))
        )["config_projection_digest"]
        != _record()["config_projection_digest"]
    )
    assert _digest({"b": "é", "a": 1}) == _digest({"a": 1, "b": "é"})
    assert _digest("é") != _digest("e\u0301")
    for value in (float("nan"), {"bad": {1, 2}}, {1: "bad"}):
        with pytest.raises(GenerationError):
            _digest(value)
    for policy in (
        PolicyConfig(
            Path("x"), annotation_names={"x": ToolAnnotationOverride(read_only=1)}
        ),
        PolicyConfig(
            Path("x"), execution_names={"x": ExecutionOverride(timeout_ms=True)}
        ),
        PolicyConfig(Path("x"), rename_names={1: "secret"}),
    ):
        with pytest.raises(GenerationError, match="Invalid values"):
            _record(policy)


def test_prewrite_and_loader_text_scope(tmp_path) -> None:
    path = tmp_path / "spec.yaml"
    path.write_bytes(SPEC.replace("\n", "\r\n").encode())
    loader = SpecLoader(str(path))
    with pytest.raises(SpecLoaderError):
        loader.loaded_text_sha256()
    loader.load_and_validate()
    assert loader.loaded_text_sha256() == hashlib.sha256(SPEC.encode()).hexdigest()
    invalid = replace(
        _settings(), behavior=replace(_settings().behavior, tool_grouping="secret")
    )
    output = tmp_path / "out"
    with pytest.raises(GenerationError, match="Invalid values"):
        generate_project(
            GenerationRequest(str(path), str(output), invalid, provenance=True)
        )
    assert not output.exists()


def test_url_is_fetched_once_and_not_disclosed(tmp_path, monkeypatch) -> None:
    calls = []

    class Response:
        text = SPEC

        def raise_for_status(self) -> None:
            pass

    def get(url, *, timeout):
        calls.append((url, timeout))
        return Response()

    monkeypatch.setattr("openapi_to_mcp.adapters.spec_loader.requests.get", get)
    url = "https://user:secret@example.test/spec?token=secret"
    output = tmp_path / "url-output"
    result = CliRunner().invoke(
        cli, ["generate", "-o", url, "-d", str(output), "-t", "stdio", "--provenance"]
    )
    assert result.exit_code == 0, result.output
    assert calls == [(url, 10)]
    provenance = json.loads((output / "generation_report.json").read_text())[
        "provenance"
    ]
    assert provenance["spec"]["source_kind"] == "url"
    assert "secret" not in json.dumps(provenance)


def test_external_reference_content_is_outside_loaded_text(
    tmp_path, monkeypatch
) -> None:
    path = tmp_path / "spec.yaml"
    external = tmp_path / "external.yaml"
    path.write_text(
        SPEC
        + "components:\n  schemas:\n    External:\n      $ref: external.yaml#/value\n",
        encoding="utf-8",
    )
    # Isolate the provenance loader from the validator, which may resolve refs itself.
    monkeypatch.setattr(
        "openapi_to_mcp.adapters.spec_loader.validate_spec", lambda _spec: None
    )
    external.write_text("value: first\n")
    loader = SpecLoader(str(path))
    loader.load_and_validate()
    before = loader.loaded_text_sha256()
    external.write_text("value: second\n")
    # No file access is needed to calculate the digest after loading.
    monkeypatch.setattr(
        Path, "open", lambda *_args, **_kwargs: pytest.fail("unexpected read")
    )
    assert loader.loaded_text_sha256() == before


def test_distribution_version_and_missing_metadata(monkeypatch) -> None:
    module = importlib.import_module("openapi_to_mcp.commands.generation_provenance")
    names = []

    def version(name):
        names.append(name)
        return "test-version"

    monkeypatch.setattr(module.metadata, "version", version)
    assert _record()["generator"] == {
        "distribution": "openapi-to-mcp-cli",
        "version": "test-version",
    }
    assert names == ["openapi-to-mcp-cli"]

    def missing(_name):
        raise module.metadata.PackageNotFoundError

    monkeypatch.setattr(module.metadata, "version", missing)
    assert _record()["generator"]["version"] is None


def test_real_cli_policy_precedence_and_error_mode_equivalence(tmp_path) -> None:
    spec = tmp_path / "spec.yaml"
    spec.write_text(SPEC, encoding="utf-8")
    policy = tmp_path / "policy.yaml"
    runner = CliRunner()

    def generate(name, policy_text, *options):
        policy.write_text(policy_text, encoding="utf-8")
        output = tmp_path / name
        result = runner.invoke(
            cli,
            [
                "generate",
                "-o",
                str(spec),
                "-d",
                str(output),
                "-t",
                "stdio",
                "--config",
                str(policy),
                "--provenance",
                *options,
            ],
        )
        assert result.exit_code == 0, result.output
        return json.loads((output / "generation_report.json").read_text())["provenance"]

    implicit_fail = generate(
        "strict", "generate:\n  tool_grouping: tag-prefix\n", "--tool-grouping", "none"
    )
    explicit_fail = generate(
        "strict-explicit",
        "generate:\n  tool_grouping: none\n  on_mapping_error: fail\n  on_schema_error: fail\n",
    )
    assert implicit_fail["resolved_options"] == explicit_fail["resolved_options"]
    assert (
        implicit_fail["config_projection_digest"]
        == explicit_fail["config_projection_digest"]
    )
    assert implicit_fail["policy_digest"] == explicit_fail["policy_digest"]
    implicit_skip = generate("non-strict", "generate:\n  strict: false\n")
    explicit_skip = generate(
        "non-strict-explicit",
        "generate:\n  strict: true\n  on_mapping_error: skip\n  on_schema_error: skip\n",
        "--no-strict",
    )
    assert implicit_skip["resolved_options"] == explicit_skip["resolved_options"]
    assert implicit_skip["resolved_options"]["on_mapping_error"] == "skip"
    assert implicit_skip["resolved_options"]["on_schema_error"] == "skip"
    assert (
        implicit_skip["config_projection_digest"]
        == explicit_skip["config_projection_digest"]
    )
    assert implicit_skip["policy_digest"] == explicit_skip["policy_digest"]
    changed = generate(
        "changed", "generate:\n  tool_grouping: none\n", "--runtime-validation", "none"
    )
    assert changed["resolved_options"]["runtime_validation"] == "none"
    assert (
        changed["config_projection_digest"] != implicit_fail["config_projection_digest"]
    )


@pytest.mark.parametrize("field", ["behavior", "transport", "identity"])
def test_invalid_settings_containers_fail_before_logging_and_writes(
    tmp_path, field
) -> None:
    spec = tmp_path / "spec.yaml"
    spec.write_text(SPEC, encoding="utf-8")
    invalid = replace(_settings(), **{field: None})
    output = tmp_path / "out"
    with pytest.raises(
        GenerationError,
        match=r"^Invalid values for generation provenance projection\.$",
    ):
        _record(config=invalid)
    with pytest.raises(
        GenerationError,
        match=r"^Invalid values for generation provenance projection\.$",
    ):
        generate_project(
            GenerationRequest(str(spec), str(output), invalid, provenance=True)
        )
    assert not output.exists()


def test_non_json_yaml_and_local_reference_target_change(tmp_path) -> None:
    path = tmp_path / "spec.yaml"
    text = (
        SPEC
        + "x-date: 2024-01-02\ncomponents:\n  schemas:\n    Item:\n      type: string\n    Alias:\n      $ref: '#/components/schemas/Item'\n"
    )
    path.write_text(text, encoding="utf-8")
    loader = SpecLoader(str(path))
    parsed = loader.load_and_validate()
    assert not isinstance(parsed["x-date"], str)
    assert loader.loaded_text_sha256() == hashlib.sha256(text.encode()).hexdigest()
    changed = text.replace("      type: string", "      type: integer")
    path.write_text(changed, encoding="utf-8")
    loader.load_and_validate()
    assert loader.loaded_text_sha256() == hashlib.sha256(changed.encode()).hexdigest()
    assert hashlib.sha256(text.encode()).hexdigest() != loader.loaded_text_sha256()


def test_missing_settings_container_is_controlled(tmp_path) -> None:
    with pytest.raises(GenerationError, match="Invalid values"):
        build_provenance(
            source_kind="file", spec_digest="a" * 64, settings=None, policy=None
        )
    with pytest.raises(GenerationError, match="Invalid values"):
        generate_project(
            GenerationRequest("unused", str(tmp_path / "out"), None, provenance=True)
        )
    assert not (tmp_path / "out").exists()
