"""Handler for string schemas."""

import logging
from typing import Any

from openapi_to_mcp.schema.handlers.base import SchemaHandler

logger = logging.getLogger(__name__)


class StringSchemaHandler(SchemaHandler):
    """Handler for string schema types."""

    def can_handle(self, schema: dict[str, Any]) -> bool:
        """Check if this handler can process the given schema."""
        return isinstance(schema, dict) and schema.get("type") == "string"

    def handle(
        self, openapi_schema: dict[str, Any], json_schema: dict[str, Any]
    ) -> None:
        """
        Process string schema and update the JSON schema accordingly.

        Handles enum, format, and string constraints.
        """
        if "type" not in json_schema:
            json_schema["type"] = "string"

        if "enum" in openapi_schema:
            json_schema["enum"] = openapi_schema["enum"]

        if "format" in openapi_schema:
            fmt = openapi_schema["format"]
            # List of known JSON Schema formats + common OpenAPI formats
            known_formats = [
                "date",
                "date-time",
                "time",
                "duration",
                "email",
                "idn-email",
                "hostname",
                "idn-hostname",
                "ipv4",
                "ipv6",
                "uri",
                "uri-reference",
                "iri",
                "iri-reference",
                "uuid",
                "json-pointer",
                "relative-json-pointer",
                "regex",
                "byte",
                "binary",
                "password",
            ]
            if fmt in known_formats:
                json_schema["format"] = fmt

        for key in ["pattern", "minLength", "maxLength"]:
            if key in openapi_schema:
                json_schema[key] = openapi_schema[key]
