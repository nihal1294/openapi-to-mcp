from openapi_to_mcp.doctor import DoctorAnalyzer


def test_doctor_analyzer_reports_unsupported_security_and_collisions() -> None:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Doctor Analyzer", "version": "1.0.0"},
        "servers": [{"url": "https://example.com"}],
        "components": {
            "securitySchemes": {"basicAuth": {"type": "http", "scheme": "basic"}}
        },
        "paths": {
            "/a-b": {
                "get": {
                    "responses": {"200": {"description": "OK"}},
                    "security": [{"basicAuth": []}],
                }
            },
            "/a_b": {"get": {"responses": {"200": {"description": "OK"}}}},
        },
    }

    report = DoctorAnalyzer(spec).analyze("inline")
    codes = {issue.code for issue in report.issues}

    assert report.exit_code() == 3
    assert "tool_name_collision" in codes
    assert "unsupported_http_auth" in codes


def test_doctor_analyzer_accepts_host_and_supported_security_schemes() -> None:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Doctor Supported", "version": "1.0.0"},
        "host": "api.example.com",
        "components": {
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer"},
                "oauthAuth": {
                    "type": "oauth2",
                    "flows": {
                        "clientCredentials": {
                            "tokenUrl": "https://example.com/token",
                            "scopes": {},
                        }
                    },
                },
                "oidcAuth": {
                    "type": "openIdConnect",
                    "openIdConnectUrl": "https://example.com/.well-known/openid",
                },
            }
        },
        "security": [{"bearerAuth": []}, "ignore-me", {"oauthAuth": []}],
        "paths": {
            "/junk": "ignore-me",
            "/pets": {
                "get": "not-a-dict",
                "post": {
                    "operationId": "createPet",
                    "responses": {"200": {"description": "OK"}},
                },
                "put": {
                    "operationId": "replacePet",
                    "responses": {"200": {"description": "OK"}},
                    "security": {"bearerAuth": []},
                },
                "patch": {
                    "operationId": "patchPet",
                    "responses": {"200": {"description": "OK"}},
                    "security": [{"oidcAuth": []}],
                },
            },
        },
    }

    report = DoctorAnalyzer(spec).analyze("inline")
    codes = {issue.code for issue in report.issues}

    assert report.exit_code() == 0
    assert "missing_base_url" not in codes
    assert "unsupported_http_auth" not in codes
    assert "unsupported_security_scheme" not in codes


def test_doctor_analyzer_reports_global_security_issue_once() -> None:
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Doctor Global Security", "version": "1.0.0"},
        "servers": [{"url": "https://example.com"}],
        "paths": {
            "/pets": {
                "get": {
                    "operationId": "listPets",
                    "responses": {"200": {"description": "OK"}},
                },
                "post": {
                    "operationId": "createPet",
                    "responses": {"200": {"description": "OK"}},
                },
            },
        },
        "security": [{"missingScheme": []}],
    }

    report = DoctorAnalyzer(spec).analyze("inline")
    issues = [
        issue for issue in report.issues if issue.code == "undefined_security_scheme"
    ]

    assert len(issues) == 1
    assert issues[0].location == "security"
