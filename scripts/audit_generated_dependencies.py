"""Audit fresh and minimum-SDK graphs rendered from the generated server template."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from scripts.generated_dependency_audit import (
    audit_findings,
    minimum_sdk_manifest,
    render_manifest,
)

_REGISTRY = "https://registry.npmjs.org"


def _npm(
    npm: str, directory: Path, arguments: list[str]
) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603 - resolved npm executable, fixed argument list
        [npm, *arguments, f"--registry={_REGISTRY}"],
        cwd=directory,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )


def audit_graph(npm: str, directory: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Resolve without lifecycle scripts and audit the complete resulting graph."""
    directory.mkdir()
    (directory / "package.json").write_text(json.dumps(manifest), encoding="utf-8")
    resolved = _npm(
        npm,
        directory,
        [
            "install",
            "--package-lock-only",
            "--include=dev",
            "--ignore-scripts",
            "--no-audit",
            "--no-fund",
        ],
    )
    if resolved.returncode != 0:
        raise ValueError(f"npm dependency resolution failed: {resolved.stderr}")
    audited = _npm(
        npm, directory, ["audit", "--json", "--ignore-scripts", "--include=dev"]
    )
    if audited.returncode not in {0, 1}:
        raise ValueError(f"npm audit command failed: {audited.stderr}")
    report = json.loads(audited.stdout)
    lock = json.loads((directory / "package-lock.json").read_text(encoding="utf-8"))
    findings = audit_findings(report, lock)
    if audited.returncode != 0 and not findings:
        raise ValueError("npm audit failed without a vulnerability report")
    return {
        "sdk_versions": {
            name: version
            for name, version in manifest["dependencies"].items()
            if name.startswith("@modelcontextprotocol/")
        },
        "findings": findings,
    }


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--transport", required=True, choices=["stdio", "streamable-http"]
    )
    parser.add_argument(
        "--runtime-validation", required=True, choices=["input", "none"]
    )
    parser.add_argument("--report-file", type=Path)
    return parser.parse_args()


def main() -> int:
    """Audit both graphs, returning nonzero for vulnerabilities or incomplete checks."""
    args = _arguments()
    npm = shutil.which("npm")
    if npm is None:
        sys.stderr.write("npm is required to audit generated dependencies\n")
        return 2
    report = {
        "schema_version": 1,
        "transport": args.transport,
        "runtime_validation": args.runtime_validation,
        "resolutions": {},
    }
    try:
        manifest = render_manifest(args.transport, args.runtime_validation)
        with TemporaryDirectory(prefix="generated-dependency-audit-") as temporary:
            for label, graph in [
                ("fresh", manifest),
                ("minimum-sdk", minimum_sdk_manifest(manifest)),
            ]:
                report["resolutions"][label] = audit_graph(
                    npm, Path(temporary) / label, graph
                )
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        sys.stderr.write(f"Dependency audit incomplete: {error}\n")
        return 2
    serialized = json.dumps(report, indent=2)
    sys.stdout.write(serialized + "\n")
    if args.report_file:
        args.report_file.parent.mkdir(parents=True, exist_ok=True)
        args.report_file.write_text(serialized + "\n", encoding="utf-8")
    return int(any(result["findings"] for result in report["resolutions"].values()))


if __name__ == "__main__":
    raise SystemExit(main())
