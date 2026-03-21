# `generate`

Use `generate` when you want a reusable generated project on disk.

## Command

```bash
openapi-to-mcp generate [OPTIONS]
```

## Options

| Option | Required | Default | Meaning |
| --- | --- | --- | --- |
| `--openapi-json`, `-o` | Yes | None | Local path or URL to a JSON or YAML OpenAPI spec |
| `--config` | No | Auto-discover `mcpgen.yaml` / `mcpgen.yml` | Policy file path for generation defaults and tool policy |
| `--output-dir`, `-d` | Yes | None | Output directory for generated files |
| `--mcp-server-name`, `-n` | No | Spec title or fallback | Generated MCP server name |
| `--mcp-server-version`, `-v` | No | Spec version or fallback | Generated MCP server version |
| `--transport`, `-t` | No | `streamable-http` | Generated transport target |
| `--host` | No | `127.0.0.1` | Host for `streamable-http` |
| `--port`, `-p` | No | `8080` | Port for `streamable-http` |
| `--mcp-endpoint` | No | `/mcp` | HTTP MCP endpoint path |
| `--strict/--no-strict` | No | `--strict` | Fail or degrade on unsupported required behavior |
| `--on-mapping-error` | No | strict=`fail`, non-strict=`skip` | How to handle non-schema operation mapping failures |
| `--on-schema-error` | No | strict=`fail`, non-strict=`skip` | How to handle schema conversion failures while mapping operations |
| `--runtime-validation` | No | `input` | Runtime validation mode compiled into the generated server (`none` or `input`) |
| `--tool-grouping` | No | `none` | Optional grouped tool naming strategy (`none` or `tag-prefix`) |

## Examples

### Local spec, stdio output

```bash
openapi-to-mcp generate \
  --openapi-json ./openapi.yaml \
  --output-dir ./generated-stdio \
  --transport stdio
```

### Remote spec, streamable HTTP output

```bash
openapi-to-mcp generate \
  --openapi-json https://petstore.swagger.io/v2/swagger.json \
  --output-dir ./generated-http \
  --transport streamable-http \
  --host 127.0.0.1 \
  --port 8080 \
  --mcp-endpoint /mcp
```

### Generate with `mcpgen.yaml` policy

```bash
openapi-to-mcp generate \
  --openapi-json ./openapi.yaml \
  --config ./mcpgen.yaml \
  --output-dir ./generated-policy
```

See [mcpgen.yaml](../guides/mcpgen-policy.md) for policy shape and precedence.

### Non-strict generation

```bash
openapi-to-mcp generate \
  --openapi-json ./openapi.yaml \
  --output-dir ./generated-loose \
  --no-strict
```

Use non-strict mode only when you accept degraded generation plus warnings in `generation_report.json`.

### Explicitly skip mapping failures in strict mode

```bash
openapi-to-mcp generate \
  --openapi-json ./openapi.yaml \
  --output-dir ./generated-partial \
  --on-mapping-error skip
```

### Explicitly fail on schema errors in non-strict mode

```bash
openapi-to-mcp generate \
  --openapi-json ./openapi.yaml \
  --output-dir ./generated-strict-schema \
  --no-strict \
  --on-schema-error fail
```

### Disable generated runtime input validation

```bash
openapi-to-mcp generate \
  --openapi-json ./openapi.yaml \
  --output-dir ./generated-no-validation \
  --runtime-validation none
```

### Generate grouped tools by first tag prefix

```bash
openapi-to-mcp generate \
  --openapi-json ./openapi.yaml \
  --output-dir ./generated-grouped \
  --tool-grouping tag-prefix
```

`tag-prefix` uses the first operation tag when available and prefixes the generated tool
name with a normalized form such as `pets_listPets`.
If the normalized tag would start with a digit, the generator prefixes it with `group_`
to keep the emitted tool name conservative.

## Generated artifacts

`generate` writes:

- `src/` TypeScript runtime files
- `.env.example`
- generated project `README.md`
- `generation_report.json`
- optional policy application from `mcpgen.yaml`
- `package.json`, `tsconfig.json`, and related build files

## `generation_report.json`

The report captures:

- `strict_mode`
- selected `transport`
- selected `tool_grouping`
- applied `policy_file` when config was used
- mapped tool count
- resolved `on_mapping_error` and `on_schema_error` modes
- skipped operations
- warnings

Use it as the machine-readable summary of what happened during generation.

## Validation rules

- `--mcp-endpoint` must start with `/`
- `--port` matters only for `streamable-http`
- generation aborts if no tools are mapped

## Common failure cases

- invalid or unreachable OpenAPI source
- strict-mode collision or unsupported mapping failure
- unusable output directory
- malformed endpoint path for `streamable-http`

## Next step

After `generate`, follow the generated project's own `README.md` or use [test-server](test-server.md) against the built server.
