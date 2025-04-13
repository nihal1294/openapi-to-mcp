"""Handler for number and integer schemas."""

import logging
from typing import Any

from openapi_to_mcp.schema.handlers.base import SchemaHandler

logger = logging.getLogger(__name__)


class NumberSchemaHandler(SchemaHandler):
    """Handler for number and integer schema types."""

    def can_handle(self, schema: dict[str, Any]) -> bool:
        """Check if this handler can process the given schema."""
        if not isinstance(schema, dict):
            return False
        schema_type = schema.get("type")
        return schema_type in ["integer", "number"]

    def handle(
        self, openapi_schema: dict[str, Any], json_schema: dict[str, Any]
    ) -> None:
        """
        Process number/integer schema and update the JSON schema accordingly.

        Handles format, numeric constraints, and exclusive min/max handling.
        """
        if "type" not in json_schema:
            json_schema["type"] = openapi_schema.get("type")

        if "format" in openapi_schema:
            json_schema["format"] = openapi_schema["format"]

        for key in ["minimum", "maximum", "multipleOf"]:
            if key in openapi_schema:
                json_schema[key] = openapi_schema[key]

        # Handle exclusiveMinimum/Maximum (OpenAPI v3 boolean vs JSON Schema number)
        if "exclusiveMinimum" in openapi_schema:
            excl_min = openapi_schema["exclusiveMinimum"]
            if isinstance(excl_min, bool):
                if excl_min and "minimum" in openapi_schema:
                    json_schema["exclusiveMinimum"] = openapi_schema["minimum"]
            elif isinstance(excl_min, (int, float)):  # Allow numeric exclusiveMinimum
                json_schema["exclusiveMinimum"] = excl_min
            else:
                json_schema.pop("exclusiveMinimum", None)

        if "exclusiveMaximum" in openapi_schema:
            excl_max = openapi_schema["exclusiveMaximum"]
            if isinstance(excl_max, bool):
                if excl_max and "maximum" in openapi_schema:
                    json_schema["exclusiveMaximum"] = openapi_schema["maximum"]
            elif isinstance(excl_max, (int, float)):  # Allow numeric exclusiveMaximum
                json_schema["exclusiveMaximum"] = excl_max
            else:
                json_schema.pop("exclusiveMaximum", None)
