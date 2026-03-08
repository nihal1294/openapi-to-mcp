from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import rich_click as click

from openapi_to_mcp.commands.generate import generate_project
from openapi_to_mcp.commands.options import add_options, run_options
from openapi_to_mcp.common.exceptions import (
    GenerationError,
    MappingError,
    NoToolsMappedError,
    SchemaError,
    SpecLoaderError,
)
from openapi_to_mcp.common.terminal import print_section, print_success_panel
from openapi_to_mcp.common.utils import parse_env_source

PLACEHOLDER_BASE_URL = "YOUR_API_BASE_URL_HERE"


def _ensure_runtime_tools() -> None:
    for tool in ("npm", "node"):
        if shutil.which(tool) is None:
            raise click.ClickException(f"Required runtime dependency not found: {tool}")


def _prepare_output_dir(
    output_dir: str | None,
) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    if output_dir:
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path, None

    temp_dir = tempfile.TemporaryDirectory(prefix="openapi-to-mcp-run-")
    return Path(temp_dir.name), temp_dir


def _copy_example_env(output_dir: Path) -> Path:
    env_path = output_dir / ".env"
    example_path = output_dir / ".env.example"
    if example_path.exists() and not env_path.exists():
        env_path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
    return env_path


def _write_env_vars(env_path: Path, variables: dict[str, str]) -> None:
    existing = (parse_env_source(str(env_path)) or {}) if env_path.exists() else {}
    merged = {**existing, **variables}
    lines = [f"{key}={value}" for key, value in sorted(merged.items())]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _meaningful_value(value: str | None) -> str | None:
    return value if value and value != PLACEHOLDER_BASE_URL else None


def _filter_runtime_env(file_env: dict[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in file_env.items()
        if _meaningful_value(value) is not None
    }


def _prepare_runtime_env(
    output_dir: Path, target_api_base_url: str | None, env_source: str | None
) -> dict[str, str]:
    env_path = _copy_example_env(output_dir)
    overrides = parse_env_source(env_source) or {}
    if target_api_base_url:
        overrides["TARGET_API_BASE_URL"] = target_api_base_url
    if overrides:
        _write_env_vars(env_path, overrides)

    file_env = (parse_env_source(str(env_path)) or {}) if env_path.exists() else {}
    runtime_file_env = _filter_runtime_env(file_env)
    resolved_base_url = (
        _meaningful_value(overrides.get("TARGET_API_BASE_URL"))
        or (runtime_file_env.get("TARGET_API_BASE_URL"))
        or _meaningful_value(os.environ.get("TARGET_API_BASE_URL"))
    )
    if not resolved_base_url:
        raise click.UsageError(
            "TARGET_API_BASE_URL is unresolved. Provide --target-api-base-url, "
            "--env-source, or a spec with servers[0].url."
        )

    runtime_env = os.environ.copy()
    runtime_env.update(runtime_file_env)
    runtime_env.update(overrides)
    runtime_env["TARGET_API_BASE_URL"] = resolved_base_url
    return runtime_env


def _run_subprocess(command: list[str], cwd: Path, env: dict[str, str]) -> None:
    try:
        subprocess.run(command, check=True, cwd=cwd, env=env)  # noqa: S603
    except subprocess.CalledProcessError as exc:
        joined = " ".join(command)
        raise click.ClickException(
            f"Command failed ({joined}): exit code {exc.returncode}"
        ) from exc


@click.command(name="run")
@add_options(run_options)
def run_server(  # noqa: PLR0913
    openapi_json: str,
    output_dir: str | None,
    mcp_server_name: str | None,
    mcp_server_version: str | None,
    transport: str,
    host: str,
    port: int | None,
    mcp_endpoint: str,
    *,
    strict: bool,
    runtime_validation: str,
    on_mapping_error: str | None,
    on_schema_error: str | None,
    target_api_base_url: str | None,
    env_source: str | None,
) -> None:
    """Generate, build, and run an MCP server directly from an OpenAPI spec."""
    temp_dir: tempfile.TemporaryDirectory[str] | None = None

    try:
        _ensure_runtime_tools()
        output_path, temp_dir = _prepare_output_dir(output_dir)
        print_section(f"Generating MCP server in {output_path}")
        generate_project(
            openapi_json=openapi_json,
            output_dir=str(output_path),
            mcp_server_name=mcp_server_name,
            mcp_server_version=mcp_server_version,
            transport=transport,
            host=host,
            port=port,
            mcp_endpoint=mcp_endpoint,
            strict=strict,
            runtime_validation=runtime_validation,
            on_mapping_error=on_mapping_error,
            on_schema_error=on_schema_error,
        )
        runtime_env = _prepare_runtime_env(output_path, target_api_base_url, env_source)
        print_section("Installing generated server dependencies")
        _run_subprocess(["npm", "install"], cwd=output_path, env=runtime_env)
        print_section("Building generated server")
        _run_subprocess(["npm", "run", "build"], cwd=output_path, env=runtime_env)
        print_success_panel(
            "Starting generated MCP server",
            [
                f"Working directory: {output_path}",
                "Press Ctrl+C to stop the server.",
            ],
        )
        _run_subprocess(["node", "build/index.js"], cwd=output_path, env=runtime_env)
    except click.ClickException:
        raise
    except KeyboardInterrupt:
        raise click.Abort from None
    except (
        GenerationError,
        MappingError,
        NoToolsMappedError,
        SchemaError,
        SpecLoaderError,
        ValueError,
    ) as exc:
        raise click.ClickException(str(exc)) from exc
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()
