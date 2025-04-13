"""Handler for schema composition keywords (allOf, anyOf, oneOf, not)."""

import logging
from typing import Any

from openapi_to_mcp.schema.handlers.base import SchemaHandler

logger = logging.getLogger(__name__)


class CompositionHandler(SchemaHandler):
    """Handler for schema composition keywords."""

    def can_handle(self, schema: dict[str, Any]) -> bool:
        """Check if this handler can process the given schema."""
        if not isinstance(schema, dict):
            return False

        return any(key in schema for key in ["allOf", "anyOf", "oneOf", "not"])

    def handle(
        self, openapi_schema: dict[str, Any], json_schema: dict[str, Any]
    ) -> None:
        """
        Process schema composition keywords and update the JSON schema accordingly.

        Handles allOf, anyOf, oneOf, and not composition keywords.
        """
        for comp_key in ["allOf", "oneOf", "anyOf", "not"]:
            comp_value = openapi_schema.get(comp_key)

            if comp_key == "not" and isinstance(comp_value, dict):
                # 'not' applies to a single schema
                json_schema[comp_key] = self.converter.convert(comp_value)
            elif comp_key != "not" and isinstance(comp_value, list):
                # Others apply to an array of schemas
                valid_items = [s for s in comp_value if isinstance(s, dict)]
                if valid_items:
                    json_schema[comp_key] = [
                        self.converter.convert(s) for s in valid_items
                    ]
