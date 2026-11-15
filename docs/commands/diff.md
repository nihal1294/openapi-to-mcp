# `diff`

Use `diff` to compare two OpenAPI specs as generated MCP tool surfaces.

It is meant for:
- release review
- CI checks around breaking MCP changes
- comparing two spec revisions before regeneration

Both inputs can be local JSON/YAML files or URLs.

## Command

```bash
openapi-to-mcp diff \
  --before-openapi-json ./specs/previous.yaml \
  --after-openapi-json ./specs/current.yaml
```

## What it reports

`diff` currently reports:
- added tools
- removed tools
- renamed tools
- input schema changes
- output schema changes
- auth changes

The comparison is based on the generated MCP surface, not a raw text diff of the OpenAPI files.

## Exit behavior

Default behavior:
- exit `0`, even if breaking changes are found

CI-friendly behavior:

```bash
openapi-to-mcp diff \
  --before-openapi-json ./specs/previous.yaml \
  --after-openapi-json ./specs/current.yaml \
  --fail-on breaking
```

With `--fail-on breaking`, the command exits `2` when breaking MCP-surface changes are present.

## JSON output

Use machine-readable output in scripts:

```bash
openapi-to-mcp diff \
  --before-openapi-json ./specs/previous.yaml \
  --after-openapi-json ./specs/current.yaml \
  --format json
```

## Notes

- A removed tool is treated as breaking.
- A renamed tool is treated as breaking.
- Input, output, and auth changes are treated as breaking.
- Added tools are treated as non-breaking.
- If either spec cannot be mapped cleanly, fix that first with `doctor`.
- If either spec produces partial mapping results, `diff` exits `1` instead of
  comparing an incomplete MCP surface.

## Comparing policies and settings

By default neither side loads a policy file, even when `mcpgen.yaml` exists in
the working directory. Supply `--before-config` and `--after-config` independently
to compare explicit policies. `--before-no-config` and `--after-no-config`
explicitly select no policy and cannot be combined with a config on the same side.
Use side-specific `--before-tool-grouping`, `--after-tool-grouping`,
`--before-tool-descriptions`, `--after-tool-descriptions`,
`--before-tool-name-policy`, and `--after-tool-name-policy` to override each
policy's corresponding generation setting. Explicit options take precedence over
policy values, then defaults. Runtime startup and global performance settings are
not compared.

Description, public title, annotations, and per-tool execution changes have
`review` impact. `--fail-on review` exits 2 for either review or breaking changes;
`--fail-on breaking` remains limited to breaking changes. JSON reports add a
`review` count and may include `review` as a change impact. Consumers should
accept this additive count and impact value. Policy error-mode settings cannot
permit a partial comparison: mapping errors and skipped schemas are fatal.
