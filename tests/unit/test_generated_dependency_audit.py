"""Dependency audits must cover generated variants and unsafe SDK floors."""

from __future__ import annotations

import pytest

from scripts.generated_dependency_audit import (
    audit_findings,
    minimum_sdk_manifest,
    render_manifest,
)


@pytest.mark.parametrize("transport", ["stdio", "streamable-http"])
@pytest.mark.parametrize("validation", ["input", "none"])
@pytest.mark.parametrize("telemetry", ["off", "opentelemetry"])
def test_audit_manifest_tracks_generated_dependency_variants(
    transport: str, validation: str, telemetry: str
) -> None:
    manifest = render_manifest(transport, validation, telemetry)
    dependencies = manifest["dependencies"]
    assert "@modelcontextprotocol/server" in dependencies
    assert ("express" in dependencies) == (transport == "streamable-http")
    assert ("@modelcontextprotocol/node" in dependencies) == (
        transport == "streamable-http"
    )
    assert ("ajv" in dependencies) == (validation == "input")
    assert ("@opentelemetry/sdk-node" in dependencies) == (telemetry == "opentelemetry")
    assert manifest["engines"]["node"] == (
        ">=22.15.0" if telemetry == "opentelemetry" else ">=22"
    )
    assert "scripts" not in manifest


def test_minimum_sdk_graph_keeps_other_dependencies_and_original_manifest() -> None:
    manifest = {
        "dependencies": {
            "@modelcontextprotocol/server": "^2.4.0",
            "@modelcontextprotocol/node": "^2.1.2",
            "axios": "^1.20.0",
        }
    }
    minimum = minimum_sdk_manifest(manifest)
    assert minimum["dependencies"] == {
        "@modelcontextprotocol/server": "2.4.0",
        "@modelcontextprotocol/node": "2.1.2",
        "axios": "^1.20.0",
    }
    assert manifest["dependencies"]["@modelcontextprotocol/server"] == "^2.4.0"


@pytest.mark.parametrize("version", ["*", ">=2.0.0", "^2.4.0-beta.1", "workspace:*"])
def test_unrecognized_sdk_floor_fails_instead_of_auditing_latest(version: str) -> None:
    with pytest.raises(ValueError, match="SDK version"):
        minimum_sdk_manifest(
            {"dependencies": {"@modelcontextprotocol/server": version}}
        )


def test_audit_reports_installed_version_advisory_and_fixed_target() -> None:
    report = {
        "auditReportVersion": 2,
        "vulnerabilities": {
            "vulnerable-package": {
                "severity": "high",
                "range": "<2.3.0",
                "nodes": ["node_modules/vulnerable-package"],
                "via": [
                    {"title": "Unsafe input", "url": "https://example.com/advisory"}
                ],
                "fixAvailable": {"name": "vulnerable-package", "version": "2.3.0"},
            }
        },
    }
    lock = {"packages": {"node_modules/vulnerable-package": {"version": "2.0.0"}}}
    findings = audit_findings(report, lock)
    assert findings == [
        {
            "package": "vulnerable-package",
            "severity": "high",
            "installed": ["2.0.0"],
            "affected": "<2.3.0",
            "advisories": [
                {"title": "Unsafe input", "url": "https://example.com/advisory"}
            ],
            "fix": {"name": "vulnerable-package", "version": "2.3.0"},
        }
    ]


def test_empty_valid_audit_is_clean() -> None:
    assert audit_findings({"auditReportVersion": 2, "vulnerabilities": {}}, {}) == []


@pytest.mark.parametrize(
    "report",
    [
        {},
        {"error": {"code": "ENETWORK"}},
        {"auditReportVersion": 3},
        {"auditReportVersion": 2, "vulnerabilities": {}, "error": {"code": "ENETWORK"}},
    ],
)
def test_failed_or_unsupported_audit_cannot_report_a_clean_graph(report: dict) -> None:
    with pytest.raises(ValueError, match="audit report"):
        audit_findings(report, {})
