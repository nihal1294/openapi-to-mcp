# MCP Inspector

The MCP Inspector is useful when you want a GUI instead of terminal-based `test-server` checks.

## When to use it

Use MCP Inspector when you want to:

- browse available tools interactively,
- send tool calls without building CLI command lines by hand,
- inspect payloads and responses visually.

Use `test-server` when you want scriptable terminal checks.

## Streamable HTTP setup

1. Start the generated server.
2. Open MCP Inspector.
3. Create a connection using the server URL, including the endpoint path.

Example:

```text
http://127.0.0.1:8080/mcp
```

## STDIO setup

Use the full server startup command.

Example:

```text
node /absolute/path/to/generated-server/build/index.js
```

If the generated server needs runtime env values, ensure they are available to the launched process.

## Suggested workflow

1. validate fast with `test-server`
2. switch to MCP Inspector for exploratory testing
3. use [Local Workflows](local-workflows.md) for repo-level regression checks
