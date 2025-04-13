"""Handler for object schemas."""

import logging
from typing import Any

from openapi_to_mcp.schema.handlers.base import SchemaHandler

logger = logging.getLogger(__name__)


class ObjectSchemaHandler(SchemaHandler):
    """Handler for object schema types."""

    def can_handle(self, schema: dict[str, Any]) -> bool:
        """Check if this handler can process the given schema."""
        schema_type = schema.get("type")
        # Handle explicit type=object or schemas with 'properties'
        return isinstance(schema, dict) and (
            schema_type == "object" or "properties" in schema
        )

    def handle(
        self, openapi_schema: dict[str, Any], json_schema: dict[str, Any]
    ) -> None:
        """
        Process object schema and update the JSON schema accordingly.

        Handles properties, required fields, and additionalProperties.
        """
        if "type" not in json_schema:
            json_schema["type"] = "object"

        json_schema["properties"] = {}
        json_schema["required"] = openapi_schema.get("required", [])

        if "properties" in openapi_schema and isinstance(
            openapi_schema["properties"], dict
        ):
            for name, prop_schema in openapi_schema["properties"].items():
                json_schema["properties"][name] = self.converter.convert(prop_schema)

        add_props = openapi_schema.get("additionalProperties")
        if isinstance(add_props, bool):
            json_schema["additionalProperties"] = add_props
        elif isinstance(add_props, dict):
            json_schema["additionalProperties"] = self.converter.convert(add_props)
