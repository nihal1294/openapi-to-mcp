VALID_OPENAPI_YAML = """
openapi: 3.0.0
info:
  title: Test API
  version: 1.0.0
paths:
  /test:
    get:
      summary: Test endpoint
      responses:
        '200':
          description: OK
"""

VALID_OPENAPI_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Mock Spec", "version": "1.0"},
    "paths": {"/test": {"get": {"summary": "Test GET"}}},
    "servers": [{"url": "http://mock.api"}],
}

VALID_MCP_TOOL = {
    "name": "get_test",
    "description": "Test GET",
    "inputSchema": {},
    "_original_method": "GET",
    "_original_path": "/test",
    "_original_parameters": [],
    "_original_request_body": None,
}
