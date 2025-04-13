"""Common functions for handling schema properties shared across schema types."""

import logging
from typing import Any

from openapi_to_mcp.schema.handlers.base import SchemaHandler

logger = logging.getLogger(__name__)


class CommonSchemaHandler(SchemaHandler):
    """Handler for common schema properties shared across schema types."""

    def can_handle(self, schema: dict[str, Any]) -> bool:
        """This handler can process any schema."""
        return isinstance(schema, dict)

    def handle(
        self, openapi_schema: dict[str, Any], json_schema: dict[str, Any]
    ) -> None:
        """Copies common keywords from OpenAPI schema to JSON schema."""
        self._copy_common_keywords(openapi_schema, json_schema)
        self._handle_nullable(openapi_schema, json_schema)

    def _copy_common_keywords(
        self, openapi_schema: dict[str, Any], json_schema: dict[str, Any]
    ) -> None:
        """Copies common keywords from OpenAPI schema to JSON schema."""
        for key in [
            "description",
            "title",
            "default",
            "example",
            "readOnly",
            "writeOnly",
            "deprecated",
        ]:
            if key in openapi_schema:
                if key == "example":
                    # JSON Schema uses 'examples' array
                    json_schema["examples"] = [openapi_schema[key]]
                else:
                    json_schema[key] = openapi_schema[key]

    def _handle_nullable(
        self, openapi_schema: dict[str, Any], json_schema: dict[str, Any]
    ) -> None:
        """Handles the OpenAPI 'nullable' keyword."""
        if openapi_schema.get("nullable", False) and "type" in json_schema:
            current_type = json_schema["type"]
            if isinstance(current_type, list):
                if "null" not in current_type:
                    json_schema["type"].append("null")
            elif current_type != "null":
                json_schema["type"] = [current_type, "null"]
