# Changelog

All notable changes to this project will be documented in this file.

**Form serialization migration:** Earlier generated servers used Axios's implicit form serializer, which could emit names such as `tags[]` and `object[key]`. Declared form encoding now uses repeated array names or comma-separated items and serializes content-mode objects as JSON. Check affected endpoints before regenerating; see the [migration guide](https://nihal1294.github.io/openapi-to-mcp/guides/form-serialization/#migration).

## [0.15.0](https://github.com/nihal1294/openapi-to-mcp/compare/v0.14.0...v0.15.0) (2026-11-15)


### Features

* support disjoint allOf form objects ([#165](https://github.com/nihal1294/openapi-to-mcp/issues/165)) ([fdc0635](https://github.com/nihal1294/openapi-to-mcp/commit/fdc06351eb1ab3634e20a30472467f01a9bbed85))


### Bug Fixes

* include reviewed migration guidance in release notes ([#164](https://github.com/nihal1294/openapi-to-mcp/issues/164)) ([8fb79f6](https://github.com/nihal1294/openapi-to-mcp/commit/8fb79f652285382fb7faed8e0ab45f30ff791726))

## [0.14.0](https://github.com/nihal1294/openapi-to-mcp/compare/v0.13.0...v0.14.0) (2026-11-15)


### ⚠ BREAKING CHANGES

* support whole-query and form serialization ([#161](https://github.com/nihal1294/openapi-to-mcp/issues/161))

### Features

* add opt-in generation provenance ([#160](https://github.com/nihal1294/openapi-to-mcp/issues/160)) ([8d4eda7](https://github.com/nihal1294/openapi-to-mcp/commit/8d4eda74a7a85d2503017b0a59831b230b3deb1d))
* support whole-query and form serialization ([#161](https://github.com/nihal1294/openapi-to-mcp/issues/161)) ([b0d9ba1](https://github.com/nihal1294/openapi-to-mcp/commit/b0d9ba1508a44e3901f478ae75396d291b45a0d0))


### Documentation

* clarify whole-query support and form migration ([#163](https://github.com/nihal1294/openapi-to-mcp/issues/163)) ([ebaac6f](https://github.com/nihal1294/openapi-to-mcp/commit/ebaac6f252f73754a027388b53063bee9acf3c8d))

## [0.13.0](https://github.com/nihal1294/openapi-to-mcp/compare/v0.12.0...v0.13.0) (2026-11-15)


### Features

* add explicit tool metadata controls ([#155](https://github.com/nihal1294/openapi-to-mcp/issues/155)) ([09ee115](https://github.com/nihal1294/openapi-to-mcp/commit/09ee11592a2b208fe2057f3cbe394aa03372e2f9))
* compare policy-adjusted tool contracts ([#158](https://github.com/nihal1294/openapi-to-mcp/issues/158)) ([3122370](https://github.com/nihal1294/openapi-to-mcp/commit/3122370feb03612c4b8ef9948a3bf80c084771e0))
* preview generated tools and catalog size ([#156](https://github.com/nihal1294/openapi-to-mcp/issues/156)) ([edb069e](https://github.com/nihal1294/openapi-to-mcp/commit/edb069e4d40ad539421691b207d442a84d3b9cf0))

## [0.12.0](https://github.com/nihal1294/openapi-to-mcp/compare/v0.11.0...v0.12.0) (2026-11-15)


### Features

* add configurable MCP tool safety annotations ([#150](https://github.com/nihal1294/openapi-to-mcp/issues/150)) ([6a36fdf](https://github.com/nihal1294/openapi-to-mcp/commit/6a36fdffc28cb16648dbfea9218729ea8ee69a58))
* add configurable upstream response byte budgets ([#151](https://github.com/nihal1294/openapi-to-mcp/issues/151)) ([2ddb0e6](https://github.com/nihal1294/openapi-to-mcp/commit/2ddb0e696e661f521ef4f1e1aa34cdd6ab111fc2))
* add optional generated runtime telemetry ([#153](https://github.com/nihal1294/openapi-to-mcp/issues/153)) ([027a21f](https://github.com/nihal1294/openapi-to-mcp/commit/027a21f2b34ef30c6d135e6fe3ea558ca7d26859))
* add read-only maintainer adoption reports ([#152](https://github.com/nihal1294/openapi-to-mcp/issues/152)) ([b257a3d](https://github.com/nihal1294/openapi-to-mcp/commit/b257a3d8bc07a660e09c21342eec8f33042dff6c))
* expand OpenAPI 3.2 compatibility and HTTP methods ([#148](https://github.com/nihal1294/openapi-to-mcp/issues/148)) ([644151c](https://github.com/nihal1294/openapi-to-mcp/commit/644151ca84ca0fa907804ea790950705b8b2d450))


### Documentation

* refresh PyPI version and download badges ([#147](https://github.com/nihal1294/openapi-to-mcp/issues/147)) ([a9a37ce](https://github.com/nihal1294/openapi-to-mcp/commit/a9a37ce362a9114762bceb1d8755a3cc64564ec4))

## [0.11.0](https://github.com/nihal1294/openapi-to-mcp/compare/v0.10.0...v0.11.0) (2026-11-14)


### ⚠ BREAKING CHANGES

* bound generated MCP tool inputs ([#144](https://github.com/nihal1294/openapi-to-mcp/issues/144))

### Features

* support upstream HTTP Basic authentication ([#143](https://github.com/nihal1294/openapi-to-mcp/issues/143)) ([a8aced1](https://github.com/nihal1294/openapi-to-mcp/commit/a8aced13c352650652c4c4a7e6b3b10f1c9d2a11))


### Bug Fixes

* audit generated dependencies and patch watcher globbing ([#145](https://github.com/nihal1294/openapi-to-mcp/issues/145)) ([481746e](https://github.com/nihal1294/openapi-to-mcp/commit/481746e3039b0728189cac22bc4be1340079c47e))
* bound generated MCP tool inputs ([#144](https://github.com/nihal1294/openapi-to-mcp/issues/144)) ([f3da9d3](https://github.com/nihal1294/openapi-to-mcp/commit/f3da9d3f766ca62cc087557c4eaa2ee863be4987))
* **deps:** bump filelock from 3.32.7 to 4.2.1 ([#133](https://github.com/nihal1294/openapi-to-mcp/issues/133)) ([59393ae](https://github.com/nihal1294/openapi-to-mcp/commit/59393aeeb9cf67b94c7d4be264dfa5f0443a2a03))
* **deps:** bump mcp from 2.2.0 to 2.3.0 in the python-runtime group ([#127](https://github.com/nihal1294/openapi-to-mcp/issues/127)) ([d35d2cc](https://github.com/nihal1294/openapi-to-mcp/commit/d35d2ccbeee97926031681603d8bbba85e327d31))
* **deps:** bump opentelemetry-api from 1.44.0 to 1.45.2 ([#139](https://github.com/nihal1294/openapi-to-mcp/issues/139)) ([ef16c89](https://github.com/nihal1294/openapi-to-mcp/commit/ef16c898885858cdb08e832ca447ef58becf927b))
* **deps:** bump pyjwt from 2.14.0 to 2.15.0 ([#134](https://github.com/nihal1294/openapi-to-mcp/issues/134)) ([90f6df5](https://github.com/nihal1294/openapi-to-mcp/commit/90f6df5fed0467967ffdbcea1a5966ab15af28d1))
* **deps:** bump virtualenv from 21.9.0 to 21.14.13 ([#130](https://github.com/nihal1294/openapi-to-mcp/issues/130)) ([8ae8ca8](https://github.com/nihal1294/openapi-to-mcp/commit/8ae8ca8280f9fa797014d2213a82a74aa2067214))
* refresh transitive security dependencies ([#141](https://github.com/nihal1294/openapi-to-mcp/issues/141)) ([5ded5df](https://github.com/nihal1294/openapi-to-mcp/commit/5ded5df3bb2c64480629c4f03927bef058e98fba))

## [0.10.0](https://github.com/nihal1294/openapi-to-mcp/compare/v0.9.3...v0.10.0) (2026-09-21)


### ⚠ BREAKING CHANGES

* add HTTP health and readiness endpoints ([#121](https://github.com/nihal1294/openapi-to-mcp/issues/121))

### Features

* add HTTP health and readiness endpoints ([#121](https://github.com/nihal1294/openapi-to-mcp/issues/121)) ([25b1aa2](https://github.com/nihal1294/openapi-to-mcp/commit/25b1aa2684b541b7e489b340e41ee39ff9bddacc))

## [0.9.3](https://github.com/nihal1294/openapi-to-mcp/compare/v0.9.2...v0.9.3) (2026-09-20)


### Bug Fixes

* diagnose unsupported Swagger 2 constructs ([#115](https://github.com/nihal1294/openapi-to-mcp/issues/115)) ([5f57c87](https://github.com/nihal1294/openapi-to-mcp/commit/5f57c87f90648a9553f83d1d06987108cfbf9607))
* honor reserved query parameter encoding ([#118](https://github.com/nihal1294/openapi-to-mcp/issues/118)) ([027ba7c](https://github.com/nihal1294/openapi-to-mcp/commit/027ba7c2953850e156067b7504ec53960e36530c))
* preserve nullable schema constraints ([#116](https://github.com/nihal1294/openapi-to-mcp/issues/116)) ([112779c](https://github.com/nihal1294/openapi-to-mcp/commit/112779cfb6cf5aa5b8ed8f1d44a75b31c917f36d))


### Documentation

* add a tested container deployment reference ([#117](https://github.com/nihal1294/openapi-to-mcp/issues/117)) ([3c771be](https://github.com/nihal1294/openapi-to-mcp/commit/3c771bea9a57c17863ad36bd20ed2841e366fe04))

## [0.9.2](https://github.com/nihal1294/openapi-to-mcp/compare/v0.9.1...v0.9.2) (2026-09-20)


### Bug Fixes

* **deps:** migrate generated servers to MCP SDK v2 ([8c41be3](https://github.com/nihal1294/openapi-to-mcp/commit/8c41be389bd1110dd6c4ac3b0997f3cc564da504))

## [0.9.1] - 2026-09-20

### Added

- Publish the Python distribution as `openapi-to-mcp-cli` while retaining the `openapi-to-mcp` command and `openapi_to_mcp` import package.
- Publish validated distributions to PyPI with GitHub Trusted Publishing and reuse the same files for GitHub Releases.

### Changed

- Update MCP client compatibility and preserve CLI result field names, including metadata.
- Require Node.js 22+ for generated servers and update generated TypeScript dependencies.
- Update AnyIO and HTTPX2 to address dependency security advisories.
- Simplify generated compiler configuration and retain behavior-focused tests.

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
