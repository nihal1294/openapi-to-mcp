"""Exception classes for the openapi-to-mcp package."""


class OpenApiMcpError(Exception):
    """Base exception class for all openapi-to-mcp errors."""


class SchemaError(OpenApiMcpError):
    """Errors related to schema conversion."""


class MappingError(OpenApiMcpError):
    """Errors related to mapping operations to tools."""


class GenerationError(OpenApiMcpError):
    """Errors related to file generation."""


class SpecLoaderError(OpenApiMcpError):
    """Errors related to loading and validating OpenAPI specifications."""


class NoToolsMappedError(OpenApiMcpError):
    """Raised when an OpenAPI spec produces no MCP tools."""

    def __init__(self, message: str, *, is_error: bool = False) -> None:
        """Store whether the no-tools outcome should fail the CLI command."""
        super().__init__(message)
        self.is_error = is_error


class PolicyConfigError(OpenApiMcpError):
    """Errors related to loading or applying `mcpgen.yaml`."""
