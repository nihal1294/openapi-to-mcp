"""Doctor command for spec-readiness diagnostics."""

from __future__ import annotations

import json
from typing import Literal

import rich_click as click

from openapi_to_mcp.adapters.spec_loader import SpecLoader
from openapi_to_mcp.common.exceptions import SpecLoaderError
from openapi_to_mcp.common.terminal import (
    print_error_panel,
    print_section,
    print_success_panel,
    print_warning_panel,
)
from openapi_to_mcp.doctor import DoctorAnalyzer, DoctorReport

OutputFormat = Literal["json", "text"]


@click.command()
@click.option(
    "--openapi-json",
    "-o",
    required=True,
    help="Path or URL to OpenAPI specification JSON or YAML file.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    show_default=True,
    help="Output format for diagnostics.",
)
def doctor(openapi_json: str, output_format: OutputFormat) -> None:
    """Inspect an OpenAPI spec for MCP-generation readiness."""
    report = _build_report(openapi_json)
    _render_report(report, output_format)
    raise click.exceptions.Exit(report.exit_code())


def _build_report(source: str) -> DoctorReport:
    try:
        spec = SpecLoader(source=source).load_and_validate()
    except SpecLoaderError as exc:
        report = DoctorReport(source=source)
        report.add_error(
            "spec_load_failed",
            str(exc),
            source,
            "Fix the spec source or validation error before generating an MCP server.",
        )
        return report
    return DoctorAnalyzer(spec).analyze(source)


def _render_report(report: DoctorReport, output_format: OutputFormat) -> None:
    if output_format == "json":
        click.echo(json.dumps(report.to_dict(), indent=2))
        return
    if not report.issues:
        print_success_panel(
            "Doctor Report",
            [
                f"Source: {report.source}",
                "No readiness issues found.",
                "Exit code: 0",
            ],
        )
        return
    _print_summary_panel(report)
    for issue in report.issues:
        _render_issue(issue.to_dict())


def _render_issue(issue: dict[str, str]) -> None:
    print_section(f"{issue['severity'].upper()}: {issue['code']}")
    click.echo(f"Location: {issue['location']}")
    click.echo(f"Issue: {issue['message']}")
    click.echo(f"Hint: {issue['hint']}")
    click.echo()


def _print_summary_panel(report: DoctorReport) -> None:
    lines = [
        f"Source: {report.source}",
        f"Errors: {report.error_count()}",
        f"Warnings: {report.warning_count()}",
        f"Exit code: {report.exit_code()}",
    ]
    if report.error_count() > 0:
        print_error_panel("Doctor Summary", lines)
        return
    print_warning_panel("Doctor Summary", lines)
