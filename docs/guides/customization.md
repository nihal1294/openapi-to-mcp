# Customization Boundary

Generated projects keep a narrow user-owned extension surface under `src/custom/`.

## Safe to edit

- `src/custom/tools.ts`
- any helper files you add under `src/custom/`

The generator bootstraps `src/custom/tools.ts` only when it is missing. Regeneration does
not overwrite files under `src/custom/`.

## Generated files

Treat these as generated and replaceable:

- `src/index.ts`
- `src/server.ts`
- `src/runtime/*.ts`
- `src/transport.ts`
- `README.md`
- `.env.example`

If you need helpers, keep them in `src/custom/` and import them from `src/custom/tools.ts`.

## Custom tool entry point

`src/custom/tools.ts` exports a single function:

```ts
export function getCustomTools(): CustomToolDefinition[] {
  return [];
}
```

Each custom tool provides:

- `tool`: the MCP tool definition exposed to clients
- `handler`: a function that returns a `CallToolResult`

## Example

```ts
import type { CustomToolDefinition } from '../runtime/generated.js';

export function getCustomTools(): CustomToolDefinition[] {
  return [
    {
      tool: {
        name: 'ping',
        description: 'Health-check tool owned by the generated project.',
        inputSchema: { type: 'object', properties: {}, required: [] },
      },
      handler: async () => ({
        content: [{ type: 'text', text: 'pong' }],
        isError: false,
      }),
    },
  ];
}
```

## Collision rules

Server startup fails if:

- a custom tool name matches a generated tool name
- the same custom tool name is registered more than once

That keeps the boundary explicit and avoids ambiguous dispatch.
