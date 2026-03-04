# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0] - 2026-03-04
### Changed
- Replaced Poetry-based environment/dependency workflow with `uv`.
- Migrated project metadata from `tool.poetry` to PEP 621 (`[project]`) with dev dependency groups.
- Updated contributor, usage, and CI runbook docs to use `uv sync` / `uv run`.
- Upgraded direct runtime/dev Python dependencies and pinned them to latest resolved versions in `pyproject.toml` + `uv.lock`.

## [0.1.0] - 2025-06-13
### Added
- Command-line tool to generate Node.js/TypeScript MCP servers from OpenAPI v3 specifications.
- Automatic mapping of OpenAPI operations to MCP tools with JSON Schema generation.
- Creation of a runnable server project using `@modelcontextprotocol/sdk`.
- Support for `stdio` and `sse` transports with configurable port for `sse`.
- Example `.env` handling and basic error mapping in the generated server.
- Integrated linting (ruff) and formatting (black).
- Unit and integration tests using `pytest`.
