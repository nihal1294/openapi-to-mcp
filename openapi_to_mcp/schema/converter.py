"""Schema converter main implementation."""

import logging
from typing import TYPE_CHECKING, Any

from openapi_to_mcp.schema.handlers.array_schema import ArraySchemaHandler
from openapi_to_mcp.schema.handlers.common import CommonSchemaHandler
from openapi_to_mcp.schema.handlers.composition import CompositionHandler
from openapi_to_mcp.schema.handlers.number_schema import NumberSchemaHandler
from openapi_to_mcp.schema.handlers.object_schema import ObjectSchemaHandler
from openapi_to_mcp.schema.handlers.reference import ReferenceHandler
from openapi_to_mcp.schema.handlers.string_schema import StringSchemaHandler

if TYPE_CHECKING:
    from openapi_to_mcp.schema.handlers.base import SchemaHandler

logger = logging.getLogger(__name__)


class SchemaConverter:
    """Converter for OpenAPI schemas to JSON Schema."""

    def __init__(self, full_spec: dict[str, Any]) -> None:
        """
        Initialize the schema converter.

        Args:
            full_spec: The complete OpenAPI specification document.
        """
        self._full_spec = full_spec

        self._handlers: list[SchemaHandler] = [
            ReferenceHandler(self),
            CompositionHandler(self),
            ObjectSchemaHandler(self),
            ArraySchemaHandler(self),
            StringSchemaHandler(self),
            NumberSchemaHandler(self),
            CommonSchemaHandler(self),  # This should be last as it's a catch-all
        ]

    @property
    def full_spec(self) -> dict[str, Any]:
        """Get the full OpenAPI spec."""
        return self._full_spec

    def convert(self, openapi_schema: dict[str, Any] | None) -> dict[str, Any]:
        """
        Convert an OpenAPI schema to a JSON Schema.

        Args:
            openapi_schema: The OpenAPI schema to convert.

        Returns:
            The converted JSON Schema.
        """
        if not isinstance(openapi_schema, dict):
            logger.debug(
                "Invalid schema input provided to converter (expected dict). Returning empty schema."
            )
            return {}

        json_schema: dict[str, Any] = {}
        is_cyclic_reference = False

        # Infer schema type if not provided
        schema_type = openapi_schema.get("type") or self._infer_type(openapi_schema)
        if schema_type:
            json_schema["type"] = schema_type

        # Apply handlers in sequence
        for handler in self._handlers:
            if handler.can_handle(openapi_schema):
                try:
                    handler.handle(openapi_schema, json_schema)
                    if json_schema.get("_is_cyclic_reference"):
                        is_cyclic_reference = True
                except Exception as e:
                    logger.warning(
                        "Error in schema handler %s: %s",
                        handler.__class__.__name__,
                        str(e),
                    )

        if is_cyclic_reference:
            json_schema["_is_cyclic_reference"] = True

        return json_schema

    def _infer_type(self, openapi_schema: dict[str, Any]) -> str | None:
        """
        Infers schema type if not explicitly provided.

        Args:
            openapi_schema: The OpenAPI schema to infer the type from.

        Returns:
            The inferred type, or None if the type cannot be inferred.
        """
        if "properties" in openapi_schema:
            return "object"
        if "items" in openapi_schema:
            return "array"
        # Add other inferences if necessary (e.g., based on keywords like 'enum')
        return None


def openapi_schema_to_json_schema(
    openapi_schema: dict[str, Any] | None,
    full_spec: dict[str, Any],
) -> dict[str, Any]:
    """
    Recursively converts an OpenAPI schema object to a JSON Schema object.

    This function maintains backward compatibility with the old interface.

    Args:
        openapi_schema: The OpenAPI schema to convert.
        full_spec: The complete OpenAPI specification document.

    Returns:
        The converted JSON Schema.
    """
    converter = SchemaConverter(full_spec)
    return converter.convert(openapi_schema)
