"""Schema converter main implementation."""

import logging
from typing import TYPE_CHECKING, Any

from openapi_to_mcp.common.exceptions import SchemaError
from openapi_to_mcp.schema.handlers.array_schema import ArraySchemaHandler
from openapi_to_mcp.schema.handlers.base import INTERNAL_CYCLIC_REFERENCE_MARKER
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

    def __init__(
        self, full_spec: dict[str, Any], *, raise_on_error: bool = False
    ) -> None:
        """
        Initialize the schema converter.

        Args:
            full_spec: The complete OpenAPI specification document.
            raise_on_error: Whether schema handler failures should raise SchemaError.
        """
        self._full_spec = full_spec
        self._ref_stack: list[str] = []
        self._raise_on_error = raise_on_error

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

    def is_ref_on_stack(self, ref_path: str) -> bool:
        """Check whether a reference is already active in the current stack."""
        return ref_path in self._ref_stack

    def push_ref(self, ref_path: str) -> None:
        """Push a reference onto the active conversion stack."""
        self._ref_stack.append(ref_path)

    def pop_ref(self, ref_path: str) -> None:
        """Pop a reference from the active conversion stack."""
        if not self._ref_stack:
            logger.warning("Reference stack empty while popping %s.", ref_path)
            return

        current_ref = self._ref_stack.pop()
        if current_ref == ref_path:
            return

        logger.warning(
            "Reference stack out of sync. Expected %s, found %s.",
            ref_path,
            current_ref,
        )
        self._repair_ref_stack(ref_path)

    def _repair_ref_stack(self, ref_path: str) -> None:
        """Reset the ref stack when ordering can no longer be trusted."""
        logger.error(
            "Resetting reference stack after mismatch while popping %s. Remaining stack: %s",
            ref_path,
            self._ref_stack,
        )
        self._ref_stack.clear()

    def convert(
        self,
        openapi_schema: dict[str, Any] | None,
        *,
        include_internal_markers: bool = False,
    ) -> dict[str, Any]:
        """
        Convert an OpenAPI schema to a JSON Schema.

        Args:
            openapi_schema: The OpenAPI schema to convert.
            include_internal_markers: Whether to keep internal helper keys.

        Returns:
            The converted JSON Schema.
        """
        if not isinstance(openapi_schema, dict):
            logger.debug(
                "Invalid schema input provided to converter (expected dict). Returning empty schema."
            )
            return {}

        json_schema: dict[str, Any] = {}
        self._set_inferred_type(openapi_schema, json_schema)
        self._apply_handlers(openapi_schema, json_schema)
        self._strip_internal_markers(
            json_schema, include_internal_markers=include_internal_markers
        )
        return json_schema

    def _set_inferred_type(
        self, openapi_schema: dict[str, Any], json_schema: dict[str, Any]
    ) -> None:
        """Infer and set the schema type when it is not explicit."""
        schema_type = openapi_schema.get("type") or self._infer_type(openapi_schema)
        if schema_type:
            json_schema["type"] = schema_type

    def _apply_handlers(
        self, openapi_schema: dict[str, Any], json_schema: dict[str, Any]
    ) -> None:
        """Apply matching handlers in sequence."""
        for handler in self._handlers:
            if not handler.can_handle(openapi_schema):
                continue
            self._run_handler(handler, openapi_schema, json_schema)

    def _run_handler(
        self,
        handler: SchemaHandler,
        openapi_schema: dict[str, Any],
        json_schema: dict[str, Any],
    ) -> None:
        """Run a single schema handler with consistent error handling."""
        try:
            handler.handle(openapi_schema, json_schema)
        except Exception as exc:
            err_msg = f"Error in schema handler {handler.__class__.__name__}: {exc}"
            if self._raise_on_error:
                raise SchemaError(err_msg) from exc
            logger.warning(err_msg)

    def _strip_internal_markers(
        self,
        json_schema: dict[str, Any],
        *,
        include_internal_markers: bool,
    ) -> None:
        """Remove internal helper keys from public conversion output."""
        if include_internal_markers:
            return
        json_schema.pop(INTERNAL_CYCLIC_REFERENCE_MARKER, None)

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
    *,
    raise_on_error: bool = False,
) -> dict[str, Any]:
    """
    Recursively converts an OpenAPI schema object to a JSON Schema object.

    This function maintains backward compatibility with the old interface.

    Args:
        openapi_schema: The OpenAPI schema to convert.
        full_spec: The complete OpenAPI specification document.
        raise_on_error: Whether schema handler failures should raise SchemaError.

    Returns:
        The converted JSON Schema.
    """
    converter = SchemaConverter(full_spec, raise_on_error=raise_on_error)
    return converter.convert(openapi_schema)
