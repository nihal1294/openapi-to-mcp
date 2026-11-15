"""CLI command for diffing MCP-surface changes between two specs."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Literal

import rich_click as click

from openapi_to_mcp.adapters.spec_loader import SpecLoader
from openapi_to_mcp.common import MappingError
from openapi_to_mcp.common.exceptions import (
    GenerationError,
    PolicyConfigError,
    SchemaError,
    SpecLoaderError,
)
from openapi_to_mcp.common.terminal import (
    print_error_panel,
    print_section,
    print_success_panel,
    print_warning_panel,
)
from openapi_to_mcp.diff import DiffAnalyzer, DiffReport
from openapi_to_mcp.mapping.tool_grouping import TOOL_GROUPING_MODES
from openapi_to_mcp.policy import load_policy_config

OutputFormat = Literal["json", "text"]

if TYPE_CHECKING:
    from openapi_to_mcp.diff.models import FailMode


@click.command()
@click.option(
    "--before-openapi-json",
    "-b",
    required=True,
    help="Old OpenAPI specification JSON or YAML path or URL.",
)
@click.option(
    "--after-openapi-json",
    "-a",
    required=True,
    help="New OpenAPI specification JSON or YAML path or URL.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    show_default=True,
    help="Output format for the diff report.",
)
@click.option(
    "--fail-on",
    type=click.Choice(["none", "breaking", "review"], case_sensitive=False),
    default="none",
    show_default=True,
    help="Exit non-zero when the selected change class is present.",
)
@click.option("--before-config", type=click.Path(dir_okay=False))
@click.option("--after-config", type=click.Path(dir_okay=False))
@click.option("--before-no-config", is_flag=True)
@click.option("--after-no-config", is_flag=True)
@click.option("--before-tool-grouping", type=click.Choice(sorted(TOOL_GROUPING_MODES)))
@click.option("--after-tool-grouping", type=click.Choice(sorted(TOOL_GROUPING_MODES)))
@click.option("--before-tool-descriptions", type=click.Choice(["spec", "method"]))
@click.option("--after-tool-descriptions", type=click.Choice(["spec", "method"]))
@click.option("--before-tool-name-policy", type=click.Choice(["preserve", "validate"]))
@click.option("--after-tool-name-policy", type=click.Choice(["preserve", "validate"]))
def diff(
    before_openapi_json: str,
    after_openapi_json: str,
    output_format: OutputFormat,
    fail_on: FailMode,
    **options: object,
) -> None:
    """Compare two OpenAPI specs as generated MCP tool surfaces."""
    report = _build_report(before_openapi_json, after_openapi_json, options)
    _render_report(report, output_format, fail_on)
    raise click.exceptions.Exit(report.exit_code(fail_on))


def _build_report(
    before_source: str, after_source: str, options: dict | None = None
) -> DiffReport:
    before_spec = _load_spec(before_source)
    after_spec = _load_spec(after_source)
    try:
        options = options or {}
        sides = {}
        for side in ("before", "after"):
            config = options.get(f"{side}_config")
            if config and options.get(f"{side}_no_config"):
                raise click.UsageError(
                    f"--{side}-config and --{side}-no-config are mutually exclusive"
                )
            sides[side] = {
                "policy": load_policy_config(config) if config else None,
                **{
                    key: options.get(f"{side}_{key}")
                    for key in (
                        "tool_grouping",
                        "tool_descriptions",
                        "tool_name_policy",
                    )
                },
            }
        analyzer = DiffAnalyzer(before_spec, after_spec)
        if not any(value for side in sides.values() for value in side.values()):
            return analyzer.analyze(before_source, after_source)
        return analyzer.analyze(
            before_source,
            after_source,
            before_options=sides["before"],
            after_options=sides["after"],
        )
    except PolicyConfigError as exc:
        raise click.ClickException(
            "Unable to load or validate the diff policy configuration."
        ) from exc
    except (
        MappingError,
        GenerationError,
        SchemaError,
        ValueError,
    ) as exc:
        err_msg = (
            f"Unable to diff MCP surface: {exc}. "
            "Run `openapi-to-mcp doctor` on both specs first."
        )
        raise click.ClickException(err_msg) from exc


def _load_spec(source: str) -> dict:
    try:
        return SpecLoader(source=source).load_and_validate()
    except SpecLoaderError as exc:
        raise click.ClickException(f"Failed to load spec `{source}`: {exc}") from exc


def _render_report(
    report: DiffReport, output_format: OutputFormat, fail_on: FailMode
) -> None:
    if output_format == "json":
        click.echo(json.dumps(report.to_dict(fail_on), indent=2))
        return
    if not report.changes:
        print_success_panel(
            "Diff Report",
            [
                f"Before: {report.before_source}",
                f"After: {report.after_source}",
                "No MCP-surface changes detected.",
                f"Exit code: {report.exit_code(fail_on)}",
            ],
        )
        return
    _print_summary(report, fail_on)
    for change in report.changes:
        _render_change(change.to_dict())


def _print_summary(report: DiffReport, fail_on: FailMode) -> None:
    lines = [
        f"Before: {report.before_source}",
        f"After: {report.after_source}",
        f"Breaking: {report.breaking_count()}",
        f"Non-breaking: {report.non_breaking_count()}",
        f"Review: {report.review_count()}",
        f"Exit code: {report.exit_code(fail_on)}",
    ]
    if report.breaking_count() > 0:
        print_error_panel("Diff Summary", lines)
        return
    print_warning_panel("Diff Summary", lines)


def _render_change(change: dict[str, object]) -> None:
    print_section(f"{_format_impact(change['impact'])}: {change['code']}")
    click.echo(f"Location: {change['location']}")
    click.echo(f"Issue: {change['message']}")
    details = change.get("details")
    if isinstance(details, dict) and details:
        click.echo(f"Details: {json.dumps(details, sort_keys=True)}")
    click.echo(f"Hint: {change['hint']}")
    click.echo()


def _format_impact(impact: object) -> str:
    value = str(impact).replace("_", "-")
    return value.upper()
