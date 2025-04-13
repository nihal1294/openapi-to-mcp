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
