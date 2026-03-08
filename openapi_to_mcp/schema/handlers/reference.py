"""Handler for schema references ($ref)."""

import logging
from typing import Any

import requests.utils

from openapi_to_mcp.schema.handlers.base import (
    INTERNAL_CYCLIC_REFERENCE_MARKER,
    SchemaHandler,
)

logger = logging.getLogger(__name__)


class ReferenceHandler(SchemaHandler):
    """Handler for $ref schema references."""

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

        if self.converter.is_ref_on_stack(ref_path):
            logger.warning(
                "Cyclic reference detected: %s. Returning placeholder.", ref_path
            )
            json_schema.update(
                {"description": f"Cyclic reference detected: {ref_path}"}
            )
            json_schema[INTERNAL_CYCLIC_REFERENCE_MARKER] = True
            return

        self.converter.push_ref(ref_path)
        try:
            resolved_schema = self.resolve_ref(ref_path)

            if self._is_resolution_error(resolved_schema):
                json_schema.update(resolved_schema)
                return

            result = self.converter.convert(
                resolved_schema, include_internal_markers=True
            )
            recursive_error = self._is_recursive_error(result)
            propagated_cycle = bool(result.pop(INTERNAL_CYCLIC_REFERENCE_MARKER, False))
            json_schema.update(result)
            if propagated_cycle:
                json_schema[INTERNAL_CYCLIC_REFERENCE_MARKER] = True
            if recursive_error:
                return
            self._add_ref_description(openapi_schema, json_schema, ref_path)
        finally:
            self.converter.pop_ref(ref_path)

    def _is_resolution_error(self, resolved_schema: dict[str, Any]) -> bool:
        """Check whether ref resolution returned an error payload."""
        return resolved_schema.get("description", "").startswith(
            ("Unresolved reference:", "Resolved reference is not an object:")
        )

    def _is_recursive_error(self, result: dict[str, Any]) -> bool:
        """Check whether recursive conversion returned an error payload."""
        return result.get("description", "").startswith(
            (
                "Unresolved reference:",
                "Cyclic reference detected:",
                "Resolved reference is not an object:",
            )
        )

    def _add_ref_description(
        self,
        openapi_schema: dict[str, Any],
        json_schema: dict[str, Any],
        ref_path: str,
    ) -> None:
        """Attach a ref-derived description when one is missing."""
        if "description" in json_schema:
            return

        original_ref_desc = openapi_schema.get("description")
        if original_ref_desc:
            json_schema["description"] = f"{original_ref_desc} (from ref: {ref_path})"
            return

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
                    raise KeyError(err_msg)  # noqa: TRY301
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
