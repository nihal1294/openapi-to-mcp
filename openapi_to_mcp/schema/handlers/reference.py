"""Handler for schema references ($ref)."""

import logging
from typing import Any

import requests.utils

from openapi_to_mcp.schema.handlers.base import SchemaConverterProtocol, SchemaHandler

logger = logging.getLogger(__name__)


class ReferenceHandler(SchemaHandler):
    """Handler for $ref schema references."""

    def __init__(self, converter: SchemaConverterProtocol) -> None:
        """Initialize the handler."""
        super().__init__(converter)
        self.visited_refs: set[str] = set()

    def can_handle(self, schema: dict[str, Any]) -> bool:
        """Check if this handler can process the given schema."""
        return isinstance(schema, dict) and "$ref" in schema

    def handle(
        self, openapi_schema: dict[str, Any], json_schema: dict[str, Any]
    ) -> None:
        """
        Process schema references and update the JSON schema accordingly.

        Handles $ref resolution and cycle detection.
        """
        ref_path = openapi_schema["$ref"]

        if ref_path in self.visited_refs:
            logger.warning(
                "Cyclic reference detected: %s. Returning placeholder.", ref_path
            )
            json_schema.update(
                {"description": f"Cyclic reference detected: {ref_path}"}
            )
            json_schema["_is_cyclic_reference"] = True
            return

        self.visited_refs.add(ref_path)

        resolved_schema = self.resolve_ref(ref_path)

        if isinstance(resolved_schema, dict) and resolved_schema.get(
            "description", ""
        ).startswith(("Unresolved reference:", "Resolved reference is not an object:")):
            json_schema.update(resolved_schema)
            return

        result = self.converter.convert(resolved_schema)

        if isinstance(result, dict):
            is_recursive_error = result.get("description", "").startswith(
                (
                    "Unresolved reference:",
                    "Cyclic reference detected:",
                    "Resolved reference is not an object:",
                )
            )

            if result.get("_is_cyclic_reference") is True:
                json_schema["_is_cyclic_reference"] = True

            if is_recursive_error:
                json_schema.update(result)
                return

        json_schema.update(result)

        if "description" not in json_schema:
            original_ref_desc = openapi_schema.get("description")
            if original_ref_desc:
                json_schema["description"] = (
                    f"{original_ref_desc} (from ref: {ref_path})"
                )
            else:
                json_schema["description"] = f"(from ref: {ref_path})"

    def resolve_ref(self, ref: str) -> dict[str, Any]:
        """
        Resolves a simple local $ref within the OpenAPI document.
        Limited support for complex or external refs. Issues warnings on failure.

        Args:
            ref: The reference string (e.g., "#/components/schemas/Pet")

        Returns:
            The resolved schema dictionary or an error object if resolution fails
        """
        if not ref.startswith("#/"):
            logger.warning(
                "Reference '%s' not resolved (external or complex refs not supported).",
                ref,
            )
            return {"description": f"Unresolved reference: {ref}"}

        parts = ref[2:].split("/")
        current: Any = self.converter.full_spec
        try:
            for part_str in parts:
                decoded_part = requests.utils.unquote(part_str)
                if isinstance(current, list):
                    current = current[int(decoded_part)]
                elif isinstance(current, dict):
                    current = current[decoded_part]
                else:
                    err_msg = (
                        f"Cannot traverse into non-dict/list element: {decoded_part}"
                    )
                    raise KeyError(err_msg)
        except (KeyError, IndexError, ValueError, TypeError) as e:
            logger.warning(
                "Reference '%s' could not be resolved: %s",
                ref,
                e.__class__.__name__,
                exc_info=True,
            )
            return {"description": f"Unresolved reference: {ref}"}
        else:
            if not isinstance(current, dict):
                logger.warning("Resolved reference '%s' is not a dictionary.", ref)
                return {"description": f"Resolved reference is not an object: {ref}"}
            return current
