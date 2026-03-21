# `mcpgen.yaml`

Use `mcpgen.yaml` when you want repeatable generation policy without turning every run
into a long CLI invocation.

## Discovery

`generate` and `run` look for these files in the current working directory:

- `mcpgen.yaml`
- `mcpgen.yml`

You can also point to a file explicitly:

```bash
openapi-to-mcp generate \
  --openapi-json ./openapi.yaml \
  --config ./configs/mcpgen.yaml \
  --output-dir ./generated-server
```

Explicit CLI values still win over config defaults.

## Supported sections

```yaml
generate:
  transport: streamable-http
  host: 127.0.0.1
  port: 8080
  mcp_endpoint: /mcp
  strict: true
  runtime_validation: input
  tool_grouping: tag-prefix
  on_mapping_error: fail
  on_schema_error: fail

tools:
  include:
    operations:
      - GET /pets
    names:
      - listPets
  exclude:
    operations:
      - DELETE /pets/{petId}
  rename:
    operations:
      GET /pets: fetchPets
    names:
      listPets: fetchPets

auth:
  operations:
    GET /pets:
      security:
        - bearerAuth: []
      security_schemes:
        bearerAuth:
          type: http
          scheme: bearer

execution:
  operations:
    GET /pets:
      max_concurrency: 4
      timeout_ms: 15000
      cache_ttl_ms: 60000
      rate_limit_per_minute: 30
```

## What each section does

### `generate`

Sets default values for generation-related options:

- `mcp_server_name`
- `mcp_server_version`
- `transport`
- `host`
- `port`
- `mcp_endpoint`
- `strict`
- `runtime_validation`
- `tool_grouping`
- `on_mapping_error`
- `on_schema_error`

These values apply only when the CLI option was not explicitly provided.

Current `tool_grouping` values:

- `none`
- `tag-prefix`

`tag-prefix` uses the first operation tag, when present, to prefix the generated tool
name with a normalized tag such as `pets_listPets`.
If the normalized tag would start with a digit, the generator prefixes it with `group_`
to keep the emitted tool name conservative.

### `tools.include` and `tools.exclude`

Filter generated tools by:

- `operations`: `METHOD /path`
- `names`: mapped tool names before rename rules are applied

If `include` is present, only matching tools survive. `exclude` is then applied on top.

### `tools.rename`

Rename a generated tool by either:

- operation key, or
- original mapped name

If a rename policy produces duplicate names, generation fails.

### `auth`

Override generated auth metadata for a specific tool or operation.

Useful cases:

- disabling auth with `security: []`
- replacing incomplete OpenAPI auth definitions
- defining the security scheme metadata required by the generated runtime

Resolution order is:

1. operation key
2. original mapped tool name
3. renamed tool name

### `execution`

Attach per-tool runtime limits to generated metadata.

Current per-tool overrides:

- `max_concurrency`
- `timeout_ms`
- `cache_ttl_ms`
- `rate_limit_per_minute`

These become generated runtime metadata and override the generated runtime defaults for
that tool only.
Caching and rate limiting are only valid for safe HTTP methods:

- `GET`
- `HEAD`
- `OPTIONS`

Generation fails if policy tries to enable `cache_ttl_ms` or `rate_limit_per_minute`
for an unsafe operation.
Use `cache_ttl_ms: 0` or `rate_limit_per_minute: 0` to disable that control for a
specific tool even when a global runtime default is enabled.
Rate limiting uses a fixed one-minute window, so quota resets at minute boundaries.

Resolution order matches `auth`:

1. operation key
2. original mapped tool name
3. renamed tool name

## Precedence

Highest to lowest precedence:

1. explicit CLI flags
2. `mcpgen.yaml` `generate` defaults
3. built-in CLI defaults

For grouped naming, explicit rename rules still win over automatic grouping. A tool that
was explicitly renamed is not prefixed again.

Tool policy sections (`tools`, `auth`, `execution`) are config-driven only.

## Failure behavior

Generation fails when:

- the config file cannot be parsed
- a config value has the wrong type
- a rename rule produces duplicate tool names
- filtering leaves no tools to generate

`generation_report.json` includes the resolved `policy_file` when policy was applied.
