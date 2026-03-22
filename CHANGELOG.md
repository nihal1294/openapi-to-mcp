# Changelog

All notable changes to this project will be documented in this file.

## [0.9.0] - 2026-03-22

### Added

- Added opt-in retry-budget and circuit-breaker controls for safe generated tools, including generated runtime config, per-tool policy overrides, and structured runtime error metadata.
- Added reviewable performance presets for generated runtimes, with transparent expansions for concurrency, queueing, timeout, caching, rate limiting, retries, and circuit breakers.
- Added generated-server end-to-end coverage for resilience controls, invalid preset startup failures, and preset precedence behavior.

### Changed

- Hardened resilience behavior so non-retryable upstream failures no longer reset accumulated circuit-breaker state.
- Clarified runtime docs and generated project docs around preset precedence, blank preset-backed env placeholders, and conservative preset cache-cap behavior.
- Hardened performance preset parsing so only declared preset names are accepted at startup.

## [0.8.0] - 2026-03-22

### Added

- Added caller-aware tool allowlists for generated runtimes, including filtered `tools/list` responses and structured denial errors for disallowed `tools/call` requests.
- Added opt-in audit and redaction hooks for generated runtimes with deterministic controls for headers, query params, cookie names, and request/response body paths.
- Added generated-server end-to-end coverage for allowlist enforcement and audit redaction behavior.

### Changed

- Hardened audit behavior so auth-derived cookie values are redacted by default, cached successes emit paired audit events, and non-HTTP failures still produce terminal response audit events.
- Clarified generated runtime and CLI docs for access-control identity handling and audit redaction behavior.

## [0.7.0] - 2026-03-22

### Added

- Added opt-in caching and rate limiting for safe generated tools using global runtime controls and per-tool policy overrides.
- Added bounded in-memory caching controls for generated runtimes, including `MCP_CACHE_MAX_ENTRIES`.
- Added generated-server end-to-end coverage for cache hits, rate limiting, and startup validation of performance controls.

### Changed

- Enforced rate limiting before cache lookup so cache hits do not bypass per-tool rate limits.
- Improved generated runtime docs and `run` CLI docs for performance controls, disable semantics, and fixed-window rate-limit behavior.
- Hardened runtime cache eviction and policy validation for performance-control configuration.

## [0.6.0] - 2026-03-21

### Added

- Added regeneration-safe customization boundaries for generated projects via preserved `src/custom/tools.ts`.
- Added richer generated tool descriptions and input examples derived from OpenAPI metadata.
- Added opt-in grouped tool naming by first tag for generated tools.

### Changed

- Improved generated-project documentation around safe customization boundaries and grouped tool naming.
- Refreshed generated runtime dependencies and hardened dotenv loading to keep stdio output protocol-safe.

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
