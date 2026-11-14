"""Manifest and advisory contracts for auditing generated npm dependencies."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

_TEMPLATES = Path(__file__).resolve().parents[1] / "openapi_to_mcp/templates"
_SDK_PACKAGES = {"@modelcontextprotocol/server", "@modelcontextprotocol/node"}
_AUDIT_REPORT_VERSION = 2
_STABLE_FLOOR = re.compile(r"[\^~]?(\d+\.\d+\.\d+)")


def render_manifest(transport: str, validation: str) -> dict[str, Any]:
    """Render the production manifest template without executable scripts."""
    environment = Environment(
        loader=FileSystemLoader(_TEMPLATES),
        undefined=StrictUndefined,
        autoescape=False,  # noqa: S701 - JSON template, not HTML
    )
    manifest = json.loads(
        environment.get_template("package.json.j2").render(
            server_name="generated-dependency-audit",
            server_version="0.0.0",
            transport=transport,
            runtime_validation=validation,
        )
    )
    manifest.pop("scripts", None)
    return manifest


def minimum_sdk_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Pin declared SDK minimums so fresh resolution cannot hide unsafe floors."""
    minimum = copy.deepcopy(manifest)
    dependencies = minimum.get("dependencies", {})
    for name in _SDK_PACKAGES & dependencies.keys():
        version = dependencies[name]
        match = _STABLE_FLOOR.fullmatch(version)
        if match is None:
            raise ValueError(f"Unsupported SDK version range for {name}: {version}")
        dependencies[name] = match.group(1)
    return minimum


def audit_findings(
    report: dict[str, Any], lock: dict[str, Any]
) -> list[dict[str, Any]]:
    """Return actionable findings, rejecting errors and unknown npm report schemas."""
    vulnerabilities = report.get("vulnerabilities")
    if (
        "error" in report
        or report.get("auditReportVersion") != _AUDIT_REPORT_VERSION
        or not isinstance(vulnerabilities, dict)
    ):
        raise ValueError(
            f"Unsupported or failed npm audit report: {report.get('error', {})}"
        )
    packages = lock.get("packages", {})
    findings = []
    for name, vulnerability in sorted(vulnerabilities.items()):
        findings.append(
            {
                "package": name,
                "severity": vulnerability["severity"],
                "installed": sorted(
                    {
                        packages[node]["version"]
                        for node in vulnerability.get("nodes", [])
                        if node in packages and "version" in packages[node]
                    }
                ),
                "affected": vulnerability.get("range", "unknown"),
                "advisories": [
                    {"title": item["title"], "url": item["url"]}
                    for item in vulnerability.get("via", [])
                    if isinstance(item, dict)
                ],
                "fix": vulnerability.get("fixAvailable", False),
            }
        )
    return findings
