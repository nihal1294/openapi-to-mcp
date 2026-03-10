"""Load `mcpgen.yaml` policy files."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from openapi_to_mcp.common.exceptions import PolicyConfigError
from openapi_to_mcp.policy.parser import parse_policy_config

if TYPE_CHECKING:
    from openapi_to_mcp.policy.models import PolicyConfig

_DEFAULT_POLICY_FILES = ("mcpgen.yaml", "mcpgen.yml")


def load_policy_config(config_path: str | None) -> PolicyConfig | None:
    """Load a policy config from an explicit path or default filenames."""
    policy_path = _resolve_policy_path(config_path)
    if policy_path is None:
        return None
    payload = _load_policy_payload(policy_path)
    return parse_policy_config(payload, policy_path)


def _resolve_policy_path(config_path: str | None) -> Path | None:
    if config_path is not None:
        path = Path(config_path).resolve()
        if not path.is_file():
            raise PolicyConfigError(f"Policy file not found: {path}")
        return path
    for filename in _DEFAULT_POLICY_FILES:
        candidate = Path(filename).resolve()
        if candidate.is_file():
            return candidate
    return None


def _load_policy_payload(policy_path: Path) -> dict[str, object]:
    try:
        payload = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
    except OSError as exc:
        raise PolicyConfigError(
            f"Failed to read policy file `{policy_path}`: {exc}"
        ) from exc
    except yaml.YAMLError as exc:
        raise PolicyConfigError(
            f"Invalid YAML in policy file `{policy_path}`: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise PolicyConfigError(
            f"Policy file `{policy_path}` must contain a top-level mapping."
        )
    return payload
