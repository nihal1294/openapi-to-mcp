import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { once } from 'node:events';
import { pathToFileURL } from 'node:url';
import { setTimeout as delay } from 'node:timers/promises';

let calls = 0;
let markSeen, markClosed;
const seen = new Promise((resolve) => { markSeen = resolve; });
const closed = new Promise((resolve) => { markClosed = resolve; });
const upstream = createServer((req, res) => {
  calls++;
  if (calls === 1) {
    markSeen();
    res.on('close', () => { if (!res.writableEnded) markClosed(); });
  } else res.writeHead(200, { 'content-type': 'application/json' }).end('{"ok":true}');
});
upstream.listen(0, '127.0.0.1'); await once(upstream, 'listening');
Object.assign(process.env, { TARGET_API_BASE_URL: `http://127.0.0.1:${upstream.address().port}`, MCP_MAX_CONCURRENCY: '1' });
const root = pathToFileURL(`${process.argv[2]}/`);
const { OpenApiMcpServer } = await import(new URL('build/server.js', root));
const { ToolExecutor } = await import(new URL('build/runtime/executor.js', root));
const { createMcpHandler } = await import(new URL('node_modules/@modelcontextprotocol/server/dist/index.mjs', root));
const { toNodeHandler } = await import(new URL('node_modules/@modelcontextprotocol/node/dist/index.mjs', root));
const executor = new ToolExecutor();
const instances = [];
const modern = createMcpHandler(() => {
  const instance = new OpenApiMcpServer();
  instance.executor = executor;
  instances.push(instance);
  return instance.server;
}, { legacy: 'reject', responseMode: 'json' });
const handle = toNodeHandler(modern);
const server = createServer((req, res) => { void handle(req, res); });
server.listen(0, '127.0.0.1'); await once(server, 'listening');
const url = `http://127.0.0.1:${server.address().port}/mcp`;
const send = (id, signal) => fetch(url, {
  method: 'POST', signal,
  headers: { 'Content-Type': 'application/json', Accept: 'application/json, text/event-stream', 'MCP-Protocol-Version': '2026-07-28', 'Mcp-Method': 'tools/call', 'Mcp-Name': 'public' },
  body: JSON.stringify({ jsonrpc: '2.0', id, method: 'tools/call', params: { name: 'public', arguments: {}, _meta: { 'io.modelcontextprotocol/protocolVersion': '2026-07-28', 'io.modelcontextprotocol/clientCapabilities': {} } } }),
});
const deadline = (promise, label) => Promise.race([promise, delay(3000).then(() => { throw new Error(`${label} timed out`); })]);
try {
  const active = new AbortController(), queued = new AbortController();
  const first = send(1, active.signal).catch((error) => error.name);
  await deadline(seen, 'upstream arrival');
  const second = send(2, queued.signal).catch((error) => error.name);
  await delay(100);
  queued.abort(); await second;
  active.abort(); await first;
  await deadline(closed, 'upstream close');
  const result = await (await send(3)).json();
  assert.equal(result.result.structuredContent.ok, true);
  assert.equal(calls, 2);
  console.log('modern HTTP cancellation passed');
} finally {
  await modern.close();
  await Promise.allSettled(instances.map((instance) => instance.close()));
  server.closeAllConnections(); await new Promise((resolve) => server.close(resolve));
  upstream.closeAllConnections(); await new Promise((resolve) => upstream.close(resolve));
}
