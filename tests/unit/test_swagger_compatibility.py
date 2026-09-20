from openapi_to_mcp.common.spec_compatibility import swagger_operation_findings


def test_swagger_findings_resolve_referenced_inherited_parameters_and_security() -> (
    None
):
    spec = {
        "swagger": "2.0",
        "parameters": {
            "SharedLimit": {"name": "limit", "in": "query", "type": "integer"},
            "Payload": {"name": "payload", "in": "body", "schema": {"type": "object"}},
            "Attachment": {"name": "file", "in": "formData", "type": "string"},
        },
        "securityDefinitions": {
            "apiKey": {"type": "apiKey", "in": "header", "name": "X-Key"}
        },
        "security": [{"apiKey": []}],
    }
    path_item = {"parameters": [{"$ref": "#/parameters/SharedLimit"}]}
    operation = {
        "parameters": [
            {"$ref": "#/parameters/Payload"},
            {"$ref": "#/parameters/Attachment"},
        ]
    }

    findings = swagger_operation_findings(spec, "get", "/pets", path_item, operation)

    assert {(finding.field, finding.location) for finding in findings} == {
        ("type", "paths./pets.parameters[0].type"),
        ("in: body", "paths./pets.get.parameters[0].in"),
        ("in: formData", "paths./pets.get.parameters[1].in"),
        ("securityDefinitions", "security"),
    }


def test_swagger_findings_ignore_unused_security_definitions_and_empty_override() -> (
    None
):
    spec = {
        "swagger": "2.0",
        "securityDefinitions": {
            "apiKey": {"type": "apiKey", "in": "header", "name": "X-Key"}
        },
        "security": [{"apiKey": []}],
    }

    assert (
        swagger_operation_findings(spec, "get", "/public", {}, {"security": []}) == []
    )


def test_swagger_findings_preserve_supported_response_only_operation() -> None:
    spec = {"swagger": "2.0"}

    assert swagger_operation_findings(spec, "get", "/status", {}, {}) == []
