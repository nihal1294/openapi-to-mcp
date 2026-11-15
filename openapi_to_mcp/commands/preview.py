"""Preview the tools that generation would publish."""

import json
import logging
from typing import Any
from urllib.parse import urlsplit

import rich_click as click

from openapi_to_mcp.adapters.spec_loader import SpecLoader
from openapi_to_mcp.commands.generation_models import GenerationBehavior
from openapi_to_mcp.commands.options import (
    add_options,
    generation_runtime_options,
    openapi_source_options,
)
from openapi_to_mcp.commands.policy_support import load_policy_and_settings
from openapi_to_mcp.common.exceptions import (
    GenerationError,
    MappingError,
    PolicyConfigError,
    SchemaError,
    SpecLoaderError,
)
from openapi_to_mcp.mapping.preparation import prepare_tools


def _bytes(value: object) -> int:
    return len(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    )


def catalog_sizes(tools: list[dict[str, Any]]) -> dict[str, Any]:
    """Measure canonical JSON and independent component byte sizes."""
    entries = [
        {
            "name": tool["name"],
            "bytes": _bytes(tool),
            "description_bytes": _bytes(tool.get("description")),
            "input_schema_bytes": _bytes(tool.get("inputSchema")),
            "output_schema_bytes": _bytes(tool.get("outputSchema")),
        }
        for tool in tools
    ]
    return {
        "total_bytes": _bytes(tools),
        "per_tool": entries,
        "largest_tools": sorted(entries, key=lambda entry: -entry["bytes"]),
    }


def _quoted(value: object) -> str:
    """Quote input-derived text without emitting terminal control characters."""
    return json.dumps(value, ensure_ascii=True)


def _decision_lines(decision: dict[str, Any]) -> list[str]:  # noqa: PLR0911
    kind = decision["kind"]
    if kind == "selection":
        lines = [
            f"{side} {match['type']} {_quoted(match['key'])}"
            for side in ("include", "exclude")
            for match in decision[f"{side}_matches"]
        ]
        if not lines:
            lines.append(
                "selected by default"
                if decision["selected"]
                else "no include selector matched"
            )
        return lines
    if kind == "description_mode":
        return [f"description mode {decision['mode']}"]
    if kind == "rename" or kind.endswith("_override"):
        action = (
            "rename"
            if kind == "rename"
            else f"{kind.removesuffix('_override')} override"
        )
        match = decision["match"].replace("_", " ")
        return [f"{action} by {match} {_quoted(decision['key'])}"]
    if kind == "grouping":
        if decision["reason"] == "policy_rename":
            return ["grouping suppressed by policy rename"]
        if decision["reason"] == "tag_prefix":
            return [f"group prefix {_quoted(decision['prefix'])}"]
        return ["grouping skipped: no usable tag"]
    if kind == "unsupported_openapi_exclusion":
        return ["excluded before mapping an unsupported OpenAPI operation"]
    return []


def _render_operations(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        provisional, final = row["provisional_name"], row["final_name"]
        names = ""
        if provisional is not None:
            names = f"; {_quoted(provisional)}"
            if final is not None and final != provisional:
                names += f" -> {_quoted(final)}"
        click.echo(
            f"  {row['method']} {_quoted(row['path'])}: {row['status']}{names}; "
            f"source {_quoted(row['source_location'])}"
        )
        for decision in row["decisions"]:
            for line in _decision_lines(decision):
                click.echo(f"    {line}")
        if row["status"] == "skipped":
            reason = row.get("skip_reason")
            if reason is not None:
                click.echo(f"    mapping skipped: {_quoted(reason)}")


# Reuse Click's generation options so defaults and parameter sources remain identical.
_preview_options = [generation_runtime_options[index] for index in (5, 6, 7, 9, 10, 11)]


@click.command()
@add_options([*openapi_source_options, *_preview_options])
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
)
@click.option("--max-catalog-bytes", type=click.IntRange(min=0))
def preview(
    openapi_json: str,
    config: str | None,
    output_format: str,
    max_catalog_bytes: int | None,
    **options: Any,  # noqa: ANN401
) -> None:
    """Preview generated public tools and their catalog size without generating files."""
    try:
        policy, values = load_policy_and_settings(options, config)
        behavior = GenerationBehavior(
            telemetry="off", runtime_validation="input", **values
        )
        loader_logger = logging.getLogger("openapi_to_mcp.adapters.spec_loader")
        old_disabled = loader_logger.disabled
        loader_logger.disabled = True
        try:
            spec = SpecLoader(source=openapi_json).load_and_validate()
        except SpecLoaderError as error:
            if urlsplit(openapi_json).scheme in {"http", "https"}:
                raise click.ClickException(
                    "Could not load or validate the OpenAPI URL."
                ) from error
            raise
        finally:
            loader_logger.disabled = old_disabled
        result = prepare_tools(spec, behavior=behavior, policy=policy, trace=True)
        catalog = catalog_sizes(result.public_tools)
        report = {
            "schema_version": 1,
            "source_kind": "url"
            if urlsplit(openapi_json).scheme in {"http", "https"}
            else "file",
            "config_present": policy is not None,
            "settings": {
                **values,
                "on_mapping_error": result.report["on_mapping_error"],
                "on_schema_error": result.report["on_schema_error"],
            },
            "tools": result.public_tools,
            "operations": result.trace,
            "warnings": result.report["warnings"],
            "skipped_operations": result.report["skipped_operations"],
            "tool_name_warnings": result.warnings,
            "catalog": catalog,
        }
        for warning in result.warnings:
            click.echo(f"Warning: {warning['message']}", err=True)
        if output_format == "json":
            click.echo(
                json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2)
            )
        else:
            click.echo(
                f"Tools: {len(result.public_tools)}\nCatalog: {catalog['total_bytes']} bytes"
            )
            click.echo("Largest tools (independent JSON component sizes):")
            for entry in catalog["largest_tools"]:
                click.echo(
                    f"  {_quoted(entry['name'])}: {entry['bytes']} bytes; "
                    f"description {entry['description_bytes']}, input schema {entry['input_schema_bytes']}, "
                    f"output schema {entry['output_schema_bytes']} bytes"
                )
            click.echo(
                "Component sizes are independent JSON values, not additive partitions."
            )
            _render_operations(result.trace or [])
        if max_catalog_bytes is not None and catalog["total_bytes"] > max_catalog_bytes:
            raise click.exceptions.Exit(2)
    except (
        SpecLoaderError,
        MappingError,
        GenerationError,
        PolicyConfigError,
        SchemaError,
        ValueError,
    ) as error:
        raise click.ClickException(str(error)) from error
