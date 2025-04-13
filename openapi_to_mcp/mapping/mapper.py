"""Maps OpenAPI operations to MCP tool definitions."""

import logging
from typing import Any

from openapi_to_mcp.common import MappingError
from openapi_to_mcp.mapping.utils import generate_tool_name
from openapi_to_mcp.schema.converter import (
    SchemaConverter,
    openapi_schema_to_json_schema,
)
from openapi_to_mcp.schema.handlers.reference import ReferenceHandler

logger = logging.getLogger(__name__)


class Mapper:
    """Maps OpenAPI operations to MCP tool definitions."""

    def __init__(self, spec: dict[str, Any]) -> None:
        """
        Initialize the mapper with the loaded OpenAPI spec.

        Args:
            spec: The complete OpenAPI specification document.

        Raises:
            MappingError: If the provided spec is not a dictionary.
        """
        if not isinstance(spec, dict):
            err_msg = "Invalid OpenAPI specification provided to Mapper."
            raise MappingError(err_msg)
        self.spec = spec
        self._schema_converter = SchemaConverter(spec)
        self.mcp_tools: list[dict[str, Any]] = []

    def map_tools(self) -> list[dict[str, Any]]:
        """
        Iterate through the OpenAPI spec and generate MCP tool definitions.

        Returns:
            A list of dictionaries, each representing an MCP tool definition.

        Raises:
            MappingError: If the 'paths' object in the spec is invalid.
        """
        self.mcp_tools = []

        paths = self.spec.get("paths", {})
        if not isinstance(paths, dict):
            err_msg = "Invalid 'paths' object in OpenAPI spec."
            raise MappingError(err_msg)

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            for method, operation in path_item.items():
                if method.lower() not in [
                    "get",
                    "post",
                    "put",
                    "delete",
                    "patch",
                    "options",
                    "head",
                    "trace",
                ] or not isinstance(operation, dict):
                    continue

                try:
                    tool_definition = self._map_operation_to_tool(
                        method, path, operation
                    )
                    self.mcp_tools.append(tool_definition)
                except Exception:
                    logger.exception(
                        "Failed to map operation %s %s", method.upper(), path
                    )

        return self.mcp_tools

    def _resolve_ref(self, ref: str) -> dict[str, Any]:
        """
        Resolve a reference using the schema converter's reference handler.

        Args:
            ref: The reference string to resolve.

        Returns:
            The resolved schema dictionary.
        """
        ref_handler = ReferenceHandler(self._schema_converter)
        return ref_handler.resolve_ref(ref)

    def _process_parameters(
        self, parameters: list[dict[str, Any]], input_schema: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Process OpenAPI parameters and update the input schema.

        Args:
            parameters: List of parameter objects from the OpenAPI spec.
            input_schema: The JSON Schema being built, to be modified in place.

        Returns:
            List of processed parameter metadata.
        """
        processed_params: list[dict[str, Any]] = []
        if not isinstance(parameters, list):
            return processed_params

        for param_maybe_ref in parameters:
            param = param_maybe_ref
            if not isinstance(param, dict):
                continue
            if "$ref" in param:
                param = self._resolve_ref(param["$ref"])
                if not isinstance(param, dict):
                    continue

            param_name = param.get("name")
            param_in = param.get("in")
            if not param_name or param_in not in ["path", "query", "header"]:
                continue

            param_schema_openapi = param.get("schema", {})
            param_schema_json = openapi_schema_to_json_schema(
                param_schema_openapi, self.spec
            )

            if "description" in param:
                param_schema_json["description"] = param["description"]

            input_schema["properties"][param_name] = param_schema_json
            if param.get("required", False):
                input_schema["required"].append(param_name)

            processed_params.append(
                {
                    "name": param_name,
                    "in": param_in,
                    "required": param.get("required", False),
                }
            )
        return processed_params

    def _process_request_body(
        self,
        request_body_maybe_ref: dict[str, Any] | None,
        input_schema: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Process the OpenAPI requestBody and update the input schema.

        Args:
            request_body_maybe_ref: The requestBody object from the OpenAPI spec.
            input_schema: The JSON Schema being built, to be modified in place.

        Returns:
            Dictionary with processed requestBody metadata or None if not applicable.
        """
        if not isinstance(request_body_maybe_ref, dict):
            return None

        request_body = request_body_maybe_ref
        if "$ref" in request_body:
            request_body = self._resolve_ref(request_body["$ref"])
            if not isinstance(request_body, dict):
                return None

        processed_request_body: dict[str, Any] | None = None
        content = request_body.get("content", {})
        if not isinstance(content, dict):
            return None

        primary_content_type: str | None = None
        body_schema_openapi: dict[str, Any] | None = None

        if "application/json" in content and isinstance(
            content["application/json"], dict
        ):
            primary_content_type = "application/json"
            body_schema_openapi = content["application/json"].get("schema")
        elif content:
            first_type = next(iter(content))
            if isinstance(content[first_type], dict):
                primary_content_type = first_type
                body_schema_openapi = content[first_type].get("schema")
                logger.info(
                    "Using '%s' as primary content type for request body (application/json not found).",
                    primary_content_type,
                )

        if primary_content_type and isinstance(body_schema_openapi, dict):
            body_schema_json = openapi_schema_to_json_schema(
                body_schema_openapi, self.spec
            )
            input_schema["properties"]["requestBody"] = body_schema_json
            if request_body.get("required", False):
                input_schema["required"].append("requestBody")
            processed_request_body = {
                "required": request_body.get("required", False),
                "content_type": primary_content_type,
            }
        elif request_body.get("required", False):
            logger.warning(
                "Required requestBody defined but no valid schema found under 'content'. Input schema may be incomplete."
            )
            processed_request_body = {"required": True, "content_type": None}

        return processed_request_body

    def _map_operation_to_tool(
        self, method: str, path: str, operation: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Map a single OpenAPI operation to an MCP tool dictionary.

        Args:
            method: The HTTP method of the operation.
            path: The URL path of the operation.
            operation: The operation object from the OpenAPI spec.

        Returns:
            Dictionary representing an MCP tool definition.
        """
        tool_name = operation.get("operationId") or generate_tool_name(method, path)
        description = operation.get("summary") or operation.get(
            "description", f"{method.upper()} operation for {path}"
        )

        input_schema: dict[str, Any] = {
            "type": "object",
            "properties": {},
            "required": [],
        }

        parameters = operation.get("parameters", [])
        if not isinstance(parameters, list):
            logger.warning(
                "Invalid 'parameters' format for %s %s (expected list, got %s). Skipping parameter processing.",
                method.upper(),
                path,
                type(parameters).__name__,
            )
            parameters = []
        processed_params = self._process_parameters(parameters, input_schema)

        request_body_maybe_ref = operation.get("requestBody")
        processed_request_body = self._process_request_body(
            request_body_maybe_ref, input_schema
        )

        if "required" in input_schema:
            input_schema["required"] = sorted(set(input_schema["required"]))

        return {
            "name": tool_name,
            "description": description,
            "inputSchema": input_schema,
            "_original_method": method.upper(),
            "_original_path": path,
            "_original_parameters": processed_params,
            "_original_request_body": processed_request_body,
        }
