"""Common utility functions used across the openapi-to-mcp package."""

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def _parse_dotenv(file_path: str) -> dict[str, str]:
    """Parses a .env file into a dictionary."""
    env_vars = {}
    try:
        with open(file_path, encoding="utf-8") as f:
            for raw_line in f:
                clean_line = raw_line.strip()
                if not clean_line or clean_line.startswith("#"):
                    continue
                if "=" not in clean_line:
                    continue
                key, value = clean_line.split("=", 1)
                key = key.strip()
                value = value.strip().strip("'\"")
                if key:
                    env_vars[key] = value
    except FileNotFoundError as err:
        raise ValueError(f".env file not found at: {file_path}") from err
    except Exception as e:
        raise ValueError(f"Failed to parse .env file '{file_path}': {e}") from e
    return env_vars


def parse_env_source(env_source: str | None) -> dict[str, str] | None:
    """
    Parses env source from JSON string, JSON file, or .env file.

    Args:
        env_source: A string containing either a JSON object, a path to a JSON file,
                   or a path to a .env file.

    Returns:
        A dictionary of environment variables, or None if env_source is None.

    Raises:
        ValueError: If the env_source cannot be parsed or the file is not found.
    """
    if not env_source:
        return None

    logger.info("Processing env source: %s", env_source)
    env_vars: dict[str, Any] | None = None

    try:
        potential_json = json.loads(env_source)
        if isinstance(potential_json, dict):
            env_vars = potential_json
            logger.info("Parsed env source as JSON string.")
        else:
            raise TypeError("JSON string is not an object.")
    except (json.JSONDecodeError, TypeError):
        logger.info("Could not parse as JSON string, attempting as file path.")
        if not os.path.exists(env_source):
            raise ValueError(f"File not found for env source: {env_source}") from None

        try:
            if env_source.lower().endswith(".json"):
                with open(env_source, encoding="utf-8") as f:
                    file_json = json.load(f)
                if not isinstance(file_json, dict):
                    raise TypeError("JSON file content is not an object.")
                env_vars = file_json
                logger.info("Loaded environment from JSON file: %s", env_source)
            else:
                env_vars = _parse_dotenv(env_source)
                logger.info("Loaded environment from .env file: %s", env_source)
        except Exception as e:
            logger.exception("Failed to load or parse env source file '%s'", env_source)
            raise ValueError(f"Failed to load or parse env source file: {e}") from e

    if env_vars is None:
        raise ValueError("Failed to parse env source.")

    try:
        return {str(k): str(v) for k, v in env_vars.items()}
    except Exception as e:
        raise ValueError(
            f"Could not convert parsed env variables to strings: {e}"
        ) from e
