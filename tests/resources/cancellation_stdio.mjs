import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { once } from 'node:events';
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
let requests = 0;
let closeSeen;
const closed = new Promise((resolve) => { closeSeen = resolve; });
let requestSeen;
const received = new Promise((resolve) => { requestSeen = resolve; });
const upstream = createServer((req, res) => {
  requests++;
  if (requests === 1) {
    requestSeen();
    res.on('close', closeSeen);
  } else res.writeHead(200, { 'content-type': 'application/json' }).end('{"ok":true}');
});
upstream.listen(0, '127.0.0.1'); await once(upstream, 'listening');
const child = spawn(process.execPath, ['build/index.js'], {
  cwd: process.argv[2], env: { ...process.env, TARGET_API_BASE_URL: `http://127.0.0.1:${upstream.address().port}`, MCP_MAX_CONCURRENCY: '1' },
  stdio: ['pipe', 'pipe', 'pipe'],
});
child.stderr.on('data', (chunk) => process.stderr.write(chunk));
const lines = createInterface({ input: child.stdout })[Symbol.asyncIterator]();
const send = (message) => child.stdin.write(`${JSON.stringify({ jsonrpc: '2.0', ...message })}\n`);
try {
  send({ id: 1, method: 'initialize', params: { protocolVersion: '2025-03-26', capabilities: {}, clientInfo: { name: 'test', version: '1' } } });
  assert.equal(JSON.parse((await lines.next()).value).id, 1);
  send({ method: 'notifications/initialized' });
  const call = (id) => send({ id, method: 'tools/call', params: { name: 'public', arguments: {} } });
  const cancel = (requestId) => send({ method: 'notifications/cancelled', params: { requestId } });
  call(2); await received;
  call(3);
  await new Promise((resolve) => setTimeout(resolve, 30));
  cancel(3); cancel(2);
  await Promise.race([closed, new Promise((_, reject) => setTimeout(() => reject(new Error('active request was not cancelled')), 2000))]);
  call(4);
  const reply = JSON.parse((await lines.next()).value);
  assert.equal(reply.id, 4);
  assert.equal(reply.result.structuredContent.ok, true);
  assert.equal(requests, 2);
  const customCall = (id, name) => send({ id, method: 'tools/call', params: { name, arguments: {} } });
  customCall(5, 'legacy');
  assert.equal(JSON.parse((await lines.next()).value).result.content[0].text, 'legacy');
  customCall(6, 'cooperative');
  customCall(7, 'status');
  let status = JSON.parse(JSON.parse((await lines.next()).value).result.content[0].text);
  assert.equal(status.started, true);
  cancel(6);
  customCall(8, 'status');
  status = JSON.parse(JSON.parse((await lines.next()).value).result.content[0].text);
  assert.equal(status.cancelled, true);
  console.log('stdio cancellation passed');
} finally {
  child.kill(); await once(child, 'exit');
  upstream.closeAllConnections(); await new Promise((resolve) => upstream.close(resolve));
}
