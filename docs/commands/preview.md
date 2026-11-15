# preview

Preview the public tool catalog without generating a project or starting a server:

```shell
openapi-to-mcp preview -o openapi.yaml --format json --tool-grouping tag-prefix
```

Preview uses the same mapping, policy discovery, grouping, description and name settings as `generate`. Explicit command-line settings take precedence over policy defaults. The ordered operation trace distinguishes early exclusions, exclusions after mapping, skips and selected operations. Overrides identify their matching key without reporting auth values.

JSON output includes the exact public tools, operation decisions, warnings, skipped operations and resolved mapping settings. Public metadata can contain input-derived descriptions, schemas and examples; treat the output as potentially sensitive. It does not contain the runtime registry or full source and policy locations.

Catalog size is the number of UTF-8 bytes in the public tools array serialized with sorted keys, compact separators, unescaped Unicode and no trailing newline. Per-tool and description, input-schema and output-schema sizes are independent JSON values, so component sizes are not an additive breakdown. Sizes do not estimate token counts. Use `--max-catalog-bytes N` to render the report and exit 2 if the total exceeds a nonnegative limit; equality succeeds. Mapping and configuration errors fail without a successful partial report.
