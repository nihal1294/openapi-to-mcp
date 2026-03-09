"""Support helpers for the `run` command."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import rich_click as click

from openapi_to_mcp.common.utils import parse_env_source

PLACEHOLDER_BASE_URL = "YOUR_API_BASE_URL_HERE"


def ensure_runtime_tools() -> None:
    """Fail early when required local runtime tools are missing."""
    for tool in ("npm", "node"):
        if shutil.which(tool) is None:
            raise click.ClickException(f"Required runtime dependency not found: {tool}")


def prepare_output_dir(
    output_dir: str | None,
) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    """Return a persistent or temporary output directory for `run`."""
    if output_dir:
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path, None

    temp_dir = tempfile.TemporaryDirectory(prefix="openapi-to-mcp-run-")
    return Path(temp_dir.name), temp_dir


def prepare_runtime_env(
    output_dir: Path,
    target_api_base_url: str | None,
    env_source: str | None,
    runtime_overrides: dict[str, str],
) -> dict[str, str]:
    """Resolve runtime environment for the generated server."""
    env_path = _copy_example_env(output_dir)
    overrides = parse_env_source(env_source) or {}
    overrides.update(runtime_overrides)
    if target_api_base_url:
        overrides["TARGET_API_BASE_URL"] = target_api_base_url
    if overrides:
        _write_env_vars(env_path, overrides)

    file_env = (parse_env_source(str(env_path)) or {}) if env_path.exists() else {}
    runtime_file_env = _filter_runtime_env(file_env)
    resolved_base_url = (
        _meaningful_value(overrides.get("TARGET_API_BASE_URL"))
        or runtime_file_env.get("TARGET_API_BASE_URL")
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


def run_subprocess(command: list[str], cwd: Path, env: dict[str, str]) -> None:
    """Run a generated-server subprocess and raise a clean CLI error on failure."""
    try:
        subprocess.run(command, check=True, cwd=cwd, env=env)  # noqa: S603
    except subprocess.CalledProcessError as exc:
        joined = " ".join(command)
        raise click.ClickException(
            f"Command failed ({joined}): exit code {exc.returncode}"
        ) from exc


def _copy_example_env(output_dir: Path) -> Path:
    env_path = output_dir / ".env"
    example_path = output_dir / ".env.example"
    if example_path.exists() and not env_path.exists():
        env_path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
    return env_path


def _write_env_vars(env_path: Path, variables: dict[str, str]) -> None:
    existing = (parse_env_source(str(env_path)) or {}) if env_path.exists() else {}
    merged = {**existing, **variables}
    lines = [
        f"{key}={_serialize_env_value(key, value)}"
        for key, value in sorted(merged.items())
    ]
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _meaningful_value(value: str | None) -> str | None:
    return value if value not in (None, "", PLACEHOLDER_BASE_URL) else None


def _filter_runtime_env(file_env: dict[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in file_env.items()
        if _meaningful_value(value) is not None
    }


def _serialize_env_value(key: str, value: str) -> str:
    if "\n" in value or "\r" in value:
        raise click.UsageError(
            f"{key} contains a newline, which cannot be written safely to .env."
        )
    return value
