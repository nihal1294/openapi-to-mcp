"""Handler for array schemas."""

import logging
from typing import Any

from openapi_to_mcp.schema.handlers.base import SchemaHandler

logger = logging.getLogger(__name__)


class ArraySchemaHandler(SchemaHandler):
    """Handler for array schema types."""

    def can_handle(self, schema: dict[str, Any]) -> bool:
        """Check if this handler can process the given schema."""
        schema_type = schema.get("type")
        # Handle explicit type=array or schemas with 'items'
        return isinstance(schema, dict) and (
            schema_type == "array" or "items" in schema
        )

    def handle(
        self, openapi_schema: dict[str, Any], json_schema: dict[str, Any]
    ) -> None:
        """
        Process array schema and update the JSON schema accordingly.

        Handles items and array constraints.
        """
        if "type" not in json_schema:
            json_schema["type"] = "array"

        json_schema["items"] = self.converter.convert(openapi_schema.get("items", {}))

        for key in ["minItems", "maxItems", "uniqueItems"]:
            if key in openapi_schema:
                json_schema[key] = openapi_schema[key]
