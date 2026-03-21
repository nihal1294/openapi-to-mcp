"""Maps OpenAPI operations to MCP tool definitions."""

import logging
from typing import Any

from openapi_to_mcp.common import MappingError, SchemaError
from openapi_to_mcp.common.error_policy import ErrorMode, resolve_error_mode
from openapi_to_mcp.mapping.output_schema import extract_output_schema
from openapi_to_mcp.mapping.tool_description import build_tool_description
from openapi_to_mcp.mapping.tool_examples import (
    add_media_example,
    add_parameter_example,
    build_input_examples,
)
from openapi_to_mcp.mapping.utils import generate_tool_name
from openapi_to_mcp.schema.converter import (
    SchemaConverter,
    openapi_schema_to_json_schema,
)
from openapi_to_mcp.schema.handlers.reference import ReferenceHandler

logger = logging.getLogger(__name__)


class Mapper:
    """Maps OpenAPI operations to MCP tool definitions."""

    def __init__(
        self,
        spec: dict[str, Any],
        *,
        strict: bool = True,
        on_mapping_error: ErrorMode | None = None,
        on_schema_error: ErrorMode | None = None,
    ) -> None:
        """
        Initialize the mapper with the loaded OpenAPI spec.

        Args:
            spec: The complete OpenAPI specification document.
            strict: Fail mapping on unsupported/invalid operation behavior.

        Raises:
            MappingError: If the provided spec is not a dictionary.
        """
        if not isinstance(spec, dict):
            err_msg = "Invalid OpenAPI specification provided to Mapper."
            raise MappingError(err_msg)
        self.spec = spec
        self.strict = strict
        self.on_mapping_error = resolve_error_mode(on_mapping_error, strict=strict)
        self.on_schema_error = resolve_error_mode(on_schema_error, strict=strict)
        self.mcp_tools: list[dict[str, Any]] = []
        self._diagnostics: list[str] = []
        self._skipped_operations: list[dict[str, str]] = []
        self._tool_name_counts: dict[str, int] = {}
        self._used_tool_names: set[str] = set()

    def map_tools(self) -> list[dict[str, Any]]:
        """
        Iterate through the OpenAPI spec and generate MCP tool definitions.

        Returns:
            A list of dictionaries, each representing an MCP tool definition.

        Raises:
            MappingError: If the 'paths' object in the spec is invalid.
        """
        self.mcp_tools = []
        self._diagnostics = []
        self._skipped_operations = []
        self._tool_name_counts = {}
        self._used_tool_names = set()

        paths = self.spec.get("paths", {})
        if not isinstance(paths, dict):
            err_msg = "Invalid 'paths' object in OpenAPI spec."
            raise MappingError(err_msg)

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            path_level_parameters = path_item.get("parameters", [])
            if not isinstance(path_level_parameters, list):
                path_level_parameters = []

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
                    merged_parameters = self._merge_parameters(
                        path_level_parameters,
                        operation.get("parameters", []),
                    )
                    tool_definition = self._map_operation_to_tool(
                        method,
                        path,
                        operation,
                        merged_parameters,
                    )
                    self.mcp_tools.append(tool_definition)
                except SchemaError as exc:
                    self._handle_schema_error(method, path, exc)
                except MappingError as exc:
                    self._handle_mapping_error(method, path, exc)
                except Exception as exc:  # noqa: BLE001
                    self._handle_mapping_error(method, path, exc)

        return self.mcp_tools

    def get_report(self) -> dict[str, Any]:
        """Get mapper warnings and skipped operations for generation report."""
        return {
            "mapped_tools": len(self.mcp_tools),
            "on_mapping_error": self.on_mapping_error,
            "on_schema_error": self.on_schema_error,
            "warnings": self._diagnostics,
            "skipped_operations": self._skipped_operations,
        }

    def _handle_mapping_error(self, method: str, path: str, exc: Exception) -> None:
        """Handle non-schema mapping failures according to the configured policy."""
        message = f"Failed to map operation {method.upper()} {path}: {exc}"
        if self.on_mapping_error == "fail":
            raise MappingError(message) from exc
        self._record_skipped_operation(method, path, str(exc), message)

    def _handle_schema_error(self, method: str, path: str, exc: SchemaError) -> None:
        """Handle schema-conversion failures according to the configured policy."""
        message = f"Schema error while mapping operation {method.upper()} {path}: {exc}"
        if self.on_schema_error == "fail":
            raise SchemaError(message) from exc
        self._record_skipped_operation(method, path, str(exc), message)

    def _record_skipped_operation(
        self, method: str, path: str, reason: str, message: str
    ) -> None:
        """Record a skipped operation and its diagnostic message."""
        logger.warning(message)
        self._diagnostics.append(message)
        self._skipped_operations.append(
            {
                "method": method.upper(),
                "path": path,
                "reason": reason,
            }
        )

    def _resolve_ref(self, ref: str) -> dict[str, Any]:
        """
        Resolve a reference using a converter dedicated to ref traversal.

        Args:
            ref: The reference string to resolve.

        Returns:
            The resolved schema dictionary.
        """
        ref_handler = ReferenceHandler(SchemaConverter(self.spec))
        return ref_handler.resolve_ref(ref)

    def _normalize_security_requirements(
        self, security_requirements_maybe: object
    ) -> list[dict[str, Any]] | None:
        """Normalize security requirements to a list of requirement objects."""
        if security_requirements_maybe is None:
            return None
        if not isinstance(security_requirements_maybe, list):
            return None

        valid_requirements: list[dict[str, Any]] = [
            item for item in security_requirements_maybe if isinstance(item, dict)
        ]
        return valid_requirements

    def _get_operation_security(
        self, operation: dict[str, Any]
    ) -> list[dict[str, Any]] | None:
        """Return operation-level security, else global security requirements."""
        if "security" in operation:
            return self._normalize_security_requirements(operation.get("security"))
        return self._normalize_security_requirements(self.spec.get("security"))

    def _build_security_schemes_for_operation(
        self, security_requirements: list[dict[str, Any]] | None
    ) -> dict[str, dict[str, Any]]:
        """Build scheme metadata map for schemes referenced by operation security."""
        if not security_requirements:
            return {}

        components = self.spec.get("components", {})
        if not isinstance(components, dict):
            return {}
        security_schemes = components.get("securitySchemes", {})
        if not isinstance(security_schemes, dict):
            return {}

        referenced_scheme_names: set[str] = set()
        for requirement in security_requirements:
            for scheme_name in requirement:
                if isinstance(scheme_name, str):
                    referenced_scheme_names.add(scheme_name)

        resolved_schemes: dict[str, dict[str, Any]] = {}
        for scheme_name in referenced_scheme_names:
            scheme = security_schemes.get(scheme_name)
            if isinstance(scheme, dict):
                resolved_schemes[scheme_name] = scheme

        return resolved_schemes

    def _merge_parameters(
        self,
        path_parameters_maybe: object,
        operation_parameters_maybe: object,
    ) -> list[dict[str, Any]]:
        """
        Merge path-level and operation-level parameters.

        Operation-level parameters override path-level parameters with same
        (name, in) pair per OpenAPI rules.
        """
        path_parameters = (
            path_parameters_maybe if isinstance(path_parameters_maybe, list) else []
        )
        operation_parameters = (
            operation_parameters_maybe
            if isinstance(operation_parameters_maybe, list)
            else []
        )

        merged: list[dict[str, Any]] = []
        index_by_key: dict[tuple[str, str], int] = {}

        for candidate in path_parameters:
            if not isinstance(candidate, dict):
                continue
            key = self._parameter_key(candidate)
            if key is None:
                continue
            index_by_key[key] = len(merged)
            merged.append(candidate)

        for candidate in operation_parameters:
            if not isinstance(candidate, dict):
                continue
            key = self._parameter_key(candidate)
            if key is None:
                merged.append(candidate)
                continue
            if key in index_by_key:
                merged[index_by_key[key]] = candidate
            else:
                index_by_key[key] = len(merged)
                merged.append(candidate)

        return merged

    def _parameter_key(self, parameter: dict[str, Any]) -> tuple[str, str] | None:
        """Build (name, in) key for parameter object or $ref parameter."""
        resolved = parameter
        if "$ref" in resolved:
            ref_path = resolved.get("$ref")
            if not isinstance(ref_path, str):
                return None
            resolved = self._resolve_ref(ref_path)
            if not isinstance(resolved, dict):
                return None

        name = resolved.get("name")
        location = resolved.get("in")
        if not isinstance(name, str) or not isinstance(location, str):
            return None

        return (name, location)

    def _ensure_unique_tool_name(self, candidate_name: str) -> str:
        """Ensure mapped tool names are unique."""
        if candidate_name not in self._used_tool_names:
            self._used_tool_names.add(candidate_name)
            self._tool_name_counts[candidate_name] = max(
                self._tool_name_counts.get(candidate_name, 0), 1
            )
            return candidate_name

        if self.on_mapping_error == "fail":
            err_msg = f"Duplicate tool name detected: {candidate_name}"
            raise MappingError(err_msg)

        count = self._tool_name_counts.get(candidate_name, 1)
        deduped_name = ""
        while True:
            count += 1
            deduped_name = f"{candidate_name}_{count}"
            if deduped_name not in self._used_tool_names:
                break

        self._tool_name_counts[candidate_name] = count
        self._used_tool_names.add(deduped_name)
        self._diagnostics.append(
            f"Duplicate tool name '{candidate_name}' deduped to '{deduped_name}'."
        )
        return deduped_name

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
            if not param_name or param_in not in ["path", "query", "header", "cookie"]:
                continue

            param_schema_openapi = param.get("schema", {})
            param_schema_json = openapi_schema_to_json_schema(
                param_schema_openapi, self.spec, raise_on_error=True
            )

            if "description" in param:
                param_schema_json["description"] = param["description"]
            add_parameter_example(param, param_schema_json, self._resolve_ref)

            input_schema["properties"][param_name] = param_schema_json
            if param.get("required", False):
                input_schema["required"].append(param_name)

            processed_params.append(
                {
                    "name": param_name,
                    "in": param_in,
                    "required": param.get("required", False),
                    "style": param.get("style"),
                    "explode": param.get("explode"),
                    "allow_reserved": param.get("allowReserved"),
                }
            )
        return processed_params

    def _process_request_body(  # noqa: C901
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
        primary_media: dict[str, Any] | None = None

        if "application/json" in content and isinstance(
            content["application/json"], dict
        ):
            primary_content_type = "application/json"
            primary_media = content["application/json"]
            body_schema_openapi = primary_media.get("schema")
        elif content:
            first_type = next(iter(content))
            if isinstance(content[first_type], dict):
                primary_content_type = first_type
                primary_media = content[first_type]
                body_schema_openapi = primary_media.get("schema")
                logger.info(
                    "Using '%s' as primary content type for request body (application/json not found).",
                    primary_content_type,
                )

        if primary_content_type and isinstance(body_schema_openapi, dict):
            body_schema_json = openapi_schema_to_json_schema(
                body_schema_openapi, self.spec, raise_on_error=True
            )
            if isinstance(primary_media, dict):
                add_media_example(primary_media, body_schema_json, self._resolve_ref)
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

    def _extract_operation_tags(self, operation: dict[str, Any]) -> list[str]:
        """Return the operation tags as a normalized string list."""
        tags = operation.get("tags", [])
        if not isinstance(tags, list):
            return []
        return [tag for tag in tags if isinstance(tag, str) and tag.strip()]

    def _map_operation_to_tool(
        self,
        method: str,
        path: str,
        operation: dict[str, Any],
        parameters: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Map a single OpenAPI operation to an MCP tool dictionary.

        Args:
            method: The HTTP method of the operation.
            path: The URL path of the operation.
            operation: The operation object from the OpenAPI spec.
            parameters: Merged operation parameters.

        Returns:
            Dictionary representing an MCP tool definition.
        """
        candidate_name = operation.get("operationId") or generate_tool_name(
            method, path
        )
        tool_name = self._ensure_unique_tool_name(candidate_name)
        description = build_tool_description(method, path, operation)

        input_schema: dict[str, Any] = {
            "type": "object",
            "properties": {},
            "required": [],
        }

        processed_params = self._process_parameters(parameters, input_schema)

        request_body_maybe_ref = operation.get("requestBody")
        processed_request_body = self._process_request_body(
            request_body_maybe_ref, input_schema
        )

        security_requirements = self._get_operation_security(operation)
        security_schemes = self._build_security_schemes_for_operation(
            security_requirements
        )

        if "required" in input_schema:
            input_schema["required"] = sorted(set(input_schema["required"]))
        input_examples = build_input_examples(input_schema)
        if input_examples:
            input_schema["examples"] = input_examples

        tool_definition = {
            "name": tool_name,
            "description": description,
            "inputSchema": input_schema,
            "_original_name": tool_name,
            "_original_method": method.upper(),
            "_original_path": path,
            "_original_tags": self._extract_operation_tags(operation),
            "_original_parameters": processed_params,
            "_original_request_body": processed_request_body,
            "_original_security": security_requirements,
            "_original_security_schemes": security_schemes,
        }
        output_schema = extract_output_schema(operation, self.spec, self._resolve_ref)
        if output_schema:
            tool_definition["outputSchema"] = output_schema
        return tool_definition
