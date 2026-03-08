"""Base class for schema type handlers."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Protocol

logger = logging.getLogger(__name__)
INTERNAL_CYCLIC_REFERENCE_MARKER = "_is_cyclic_reference"


class SchemaConverterProtocol(Protocol):
    """Protocol defining the interface for SchemaConverter.

    This allows handlers to call back to the main converter without
    creating circular imports.
    """

    def convert(
        self,
        openapi_schema: dict[str, Any],
        *,
        include_internal_markers: bool = False,
    ) -> dict[str, Any]:
        """Convert OpenAPI schema to JSON Schema."""
        ...

    @property
    def full_spec(self) -> dict[str, Any]:
        """Get the full OpenAPI spec."""
        ...

    def is_ref_on_stack(self, ref_path: str) -> bool:
        """Check whether a reference is already active in the current stack."""
        ...

    def push_ref(self, ref_path: str) -> None:
        """Push a reference onto the active conversion stack."""
        ...

    def pop_ref(self, ref_path: str) -> None:
        """Pop a reference from the active conversion stack."""
        ...


class SchemaHandler(ABC):
    """Base class for all schema type handlers."""

    def __init__(self, converter: SchemaConverterProtocol) -> None:
        """Initialize the handler with a reference to the converter."""
        self.converter = converter

    @abstractmethod
    def can_handle(self, schema: dict[str, Any]) -> bool:
        """
        Check if this handler can process the given schema.

        Args:
            schema: The OpenAPI schema to check

        Returns:
            True if this handler can process the schema, False otherwise
        """
        ...

    @abstractmethod
    def handle(
        self, openapi_schema: dict[str, Any], json_schema: dict[str, Any]
    ) -> None:
        """
        Process the schema and update the JSON schema accordingly.

        Args:
            openapi_schema: The OpenAPI schema to process
            json_schema: The JSON schema being built, to be modified in place
        """
        ...
