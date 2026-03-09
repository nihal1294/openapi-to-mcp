# `doctor`

Use `doctor` when you want to assess whether an OpenAPI spec is likely to generate a clean MCP server before running `generate`.

## Command

```bash
openapi-to-mcp doctor [OPTIONS]
```

## Options

| Option | Required | Default | Meaning |
| --- | --- | --- | --- |
| `--openapi-json`, `-o` | Yes | None | Local path or URL to a JSON or YAML OpenAPI spec |
| `--format` | No | `text` | Output format: `text` or `json` |

## Exit codes

| Exit code | Meaning |
| --- | --- |
| `0` | No issues found |
| `2` | Warnings only |
| `3` | One or more blocking errors |

## Current checks

`doctor` currently reports:

- missing default base URL information
- missing `operationId`
- generated tool-name collisions
- undefined referenced security schemes
- unsupported auth schemes such as HTTP Basic
- risky `oneOf` or `anyOf` usage in request or response schemas
- missing HTTP operations under `paths`

## Examples

### Human-readable report

```bash
openapi-to-mcp doctor --openapi-json ./openapi.yaml
```

### JSON report for automation

```bash
openapi-to-mcp doctor \
  --openapi-json ./openapi.yaml \
  --format json
```

## How to use the result

- Fix `error` issues before treating the spec as generation-ready.
- Review `warning` issues before relying on the generated tool surface in production.
- Use `--format json` when you want to feed diagnostics into CI or another script.
