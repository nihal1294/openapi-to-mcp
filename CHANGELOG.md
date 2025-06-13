# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2025-06-13
### Added
- Command-line tool to generate Node.js/TypeScript MCP servers from OpenAPI v3 specifications.
- Automatic mapping of OpenAPI operations to MCP tools with JSON Schema generation.
- Creation of a runnable server project using `@modelcontextprotocol/sdk`.
- Support for `stdio` and `sse` transports with configurable port for `sse`.
- Example `.env` handling and basic error mapping in the generated server.
- Integrated linting (ruff) and formatting (black).
- Unit and integration tests using `pytest`.
