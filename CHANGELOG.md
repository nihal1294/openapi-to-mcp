# Changelog

All notable changes to this project will be documented in this file.

## [0.5.0] - 2026-03-11

### Added

- Added `openapi-to-mcp doctor` for pre-generation readiness diagnostics with clean warning and error exit codes.
- Added `openapi-to-mcp diff` for MCP-surface change analysis between two OpenAPI specs.
- Added `mcpgen.yaml` / `mcpgen.yml` support for repeatable generation policy, including defaults, tool filtering, renames, auth overrides, and per-tool execution overrides.

### Changed

- Improved CLI and generated-project docs to cover diagnostics, diffing, and policy-driven generation workflows.
- Hardened config validation and policy failure handling for repeatable generation workflows.

## [0.4.0] - 2026-03-09

### Added

- Added output schema emission for object-shaped success responses and structured JSON tool results in generated runtimes.
- Added generated runtime input validation controls with `--runtime-validation {none,input}`.
- Added structured in-band tool error metadata for validation, auth, upstream, and runtime failures.
- Added startup configuration validation, runtime override support, and request ID observability for generated runtimes.
- Added a GitHub Pages docs site with install-first command and guide documentation.

### Changed

- Modularized the generated TypeScript runtime into focused `src/runtime/*` modules instead of a monolithic `server.ts`.
- Split public MCP tool definitions from internal execution metadata in generated servers.
- Improved generation controls with explicit mapping-error and schema-error policies.
- Hardened generated-server and CLI end-to-end coverage around auth, runtime validation, observability, and contract behavior.

## [0.3.0] - 2026-03-07

### Added

- Added auth-path generated-server E2E coverage for apiKey header/query/cookie and bearer-token flows.
- Added `openapi-to-mcp run` to generate, build, and run an MCP server directly from an OpenAPI spec.
- Added a CLI E2E matrix runner for `generate`, `run`, and `test-server`, with local and CI entrypoints.

### Changed

- Upgraded the CLI experience with `rich-click`, `rich`, and `structlog`.
- Refreshed README and usage examples to reflect the current generate/run/test workflow.
- Closed the remaining P0 implementation scope and aligned required checks with the current CI surface.

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
