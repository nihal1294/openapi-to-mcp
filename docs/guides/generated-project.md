# Generated Project

A generated project is a standalone Node.js/TypeScript MCP server.

## Typical output

```text
<output-dir>/
  README.md
  package.json
  tsconfig.json
  .env.example
  generation_report.json
  src/
```

## Key files

- `src/index.ts`: runtime entrypoint
- `src/server.ts`: generated tool execution runtime
- `src/transport.ts`: selected transport implementation
- `.env.example`: generated runtime and auth placeholders
- `generation_report.json`: warnings, skipped operations, mapped tool count
- generated `README.md`: build/run instructions for the emitted project

## Transport model

Only two generation targets exist:

- `stdio`
- `streamable-http`

SSE generation is intentionally gone.

## Runtime behavior included today

- parameter metadata for serialization
- generated security scheme env resolution
- bounded concurrency and queue controls
- tool timeout with abort propagation
- streamable HTTP host and origin allowlist handling
- object-shaped response schemas emitted as MCP `outputSchema`
- structured JSON object results returned as `structuredContent`

## `generation_report.json`

Use the report to check:

- whether strict mode was enabled
- selected transport
- mapped tool count
- skipped operations
- warnings emitted during generation
