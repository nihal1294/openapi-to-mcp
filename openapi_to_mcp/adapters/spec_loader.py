import logging
from pathlib import Path

import requests
import yaml
from openapi_spec_validator import validate as validate_spec

from openapi_to_mcp.common.exceptions import SpecLoaderError

logger = logging.getLogger(__name__)


class SpecLoader:
    """Handles loading and validation of OpenAPI specifications from files or URLs."""

    def __init__(self, source: str) -> None:
        """
        Initialize the spec loader with a source.

        Args:
            source: Path or URL to the OpenAPI specification
        """
        self.source = source
        self.spec = None
        self._content = None

    def load_and_validate(self) -> dict:
        """
        Load the OpenAPI spec from the source and validate it.

        Returns:
            The loaded and validated specification dictionary.

        Raises:
            SpecLoaderError: If loading or validation fails.
        """
        logger.info("Loading OpenAPI spec from: %s", self.source)
        self._load_content()
        self._parse_and_validate()
        logger.info("OpenAPI spec loaded and validated successfully.")
        return self.spec

    def _load_content(self) -> None:
        """
        Load the raw content from file or URL.

        Raises:
            SpecLoaderError: If loading fails.
        """
        if self.source.startswith(("http://", "https://")):
            self._load_from_url()
        else:
            self._load_from_file()

    def _load_from_url(self) -> None:
        """
        Load content from a URL.

        Raises:
            SpecLoaderError: If the URL request fails.
        """
        try:
            logger.debug("Fetching spec from URL: %s", self.source)
            response = requests.get(self.source, timeout=10)
            response.raise_for_status()
            self._content = response.text
            logger.debug("Successfully fetched spec from URL.")
        except requests.exceptions.Timeout as e:
            logger.exception(
                "Timeout occurred while fetching spec from URL: %s", self.source
            )
            err_msg = f"Timeout fetching OpenAPI spec from URL '{self.source}'"
            raise SpecLoaderError(err_msg) from e
        except requests.exceptions.RequestException as e:
            logger.exception("Error fetching spec from URL '%s'", self.source)
            err_msg = f"Error fetching OpenAPI spec from URL '{self.source}': {e}"
            raise SpecLoaderError(err_msg) from e

    def _load_from_file(self) -> None:
        """
        Load content from a file.

        Raises:
            SpecLoaderError: If the file cannot be read.
        """
        try:
            source_path = Path(self.source)
            logger.debug("Reading spec from file: %s", source_path)
            if not source_path.is_file():
                raise FileNotFoundError(f"File not found: {source_path}")
            with source_path.open("r", encoding="utf-8") as f:
                self._content = f.read()
            logger.debug("Successfully read spec from file.")
        except FileNotFoundError as e:
            logger.exception("OpenAPI spec file not found at '%s'", self.source)
            err_msg = f"OpenAPI spec file not found at '{self.source}'"
            raise SpecLoaderError(err_msg) from e
        except Exception as e:
            logger.exception("Error reading OpenAPI spec file '%s'", self.source)
            err_msg = f"Error reading OpenAPI spec file '{self.source}': {e}"
            raise SpecLoaderError(err_msg) from e

    def _parse_and_validate(self) -> None:
        """
        Parse the loaded content and validate the spec.

        Raises:
            SpecLoaderError: If parsing or validation fails.
        """
        if self._content is None:
            logger.error("Internal error: Spec content not loaded before parsing.")
            err_msg = "Internal error: Spec content not loaded before parsing."
            raise SpecLoaderError(err_msg)

        try:
            logger.debug("Parsing spec content (YAML/JSON).")
            self.spec = yaml.safe_load(self._content)
            if not isinstance(self.spec, dict):
                err_msg = "Parsed specification is not a valid dictionary structure."
                exception = SpecLoaderError(err_msg)
                logger.error(err_msg, exc_info=exception)
                raise exception

            logger.debug("Validating OpenAPI spec structure.")
            validate_spec(self.spec)
            logger.debug("OpenAPI spec structure validation successful.")

        except yaml.YAMLError as e:
            logger.exception("Error parsing OpenAPI spec content (YAML/JSON)")
            err_msg = f"Error parsing OpenAPI spec content (YAML/JSON): {e}"
            raise SpecLoaderError(err_msg) from e
        except Exception as e:
            logger.exception("OpenAPI spec validation failed")
            err_msg = f"OpenAPI spec validation failed: {e}"
            raise SpecLoaderError(err_msg) from e
