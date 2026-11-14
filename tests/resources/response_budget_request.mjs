import { createServer } from 'node:http';
import { once } from 'node:events';
import { readFileSync } from 'node:fs';
import { gzipSync } from 'node:zlib';
import { pathToFileURL } from 'node:url';
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';

const scenario = JSON.parse(readFileSync(0, 'utf8'));
let requests = 0;
let closed = false;
let chunksSent = 0;
const upstream = createServer((req, res) => {
  requests++;
  if (scenario.redirect && req.url !== '/redirected') { res.writeHead(302, { location: '/redirected' }); res.end(); return; }
  res.on('close', () => { closed = true; });
  const bytes = Buffer.from(scenario.body ?? '');
  const body = scenario.gzip ? gzipSync(bytes) : bytes;
  const interrupt = scenario.interrupt && (scenario.interrupt === 'always' || requests === 1);
  res.writeHead(interrupt ? (scenario.interruptStatus ?? 200) : (scenario.status ?? 200), {
    'content-type': scenario.contentType ?? 'application/json',
    ...(scenario.gzip ? { 'content-encoding': 'gzip' } : {}),
    ...(interrupt ? { 'content-length': 100 } : scenario.knownLength ? { 'content-length': body.length } : {}),
  });
  if (interrupt) {
    res.write('abc');
    setTimeout(() => res.destroy(), 20);
  } else if (scenario.longStream) {
    const timer = setInterval(() => {
      if (res.destroyed || chunksSent >= 100) { clearInterval(timer); return; }
      chunksSent++;
      res.write(Buffer.alloc(1024, 120));
    }, 2);
    res.on('close', () => clearInterval(timer));
  } else if (scenario.slow) {
    res.write(body.subarray(0, 1));
    setTimeout(() => { if (!res.destroyed) res.end(body.subarray(1)); }, 300);
  } else if (scenario.chunked) {
    res.write(body.subarray(0, 2));
    setTimeout(() => res.end(body.subarray(2)), 5);
  } else res.end(body);
});
upstream.listen(0, '127.0.0.1');
await once(upstream, 'listening');
try {
  Object.assign(process.env, scenario.env, {
    TARGET_API_BASE_URL: `http://127.0.0.1:${upstream.address().port}`,
    MCP_AUDIT_MODE: 'logs',
  });
  const results = [];
  if (scenario.protocol) {
    const child = spawn(process.execPath, ['build/index.js'], { cwd: process.argv[2], env: process.env, stdio: ['pipe', 'pipe', 'pipe'] });
    child.stderr.on('data', (chunk) => process.stderr.write(chunk));
    const lines = createInterface({ input: child.stdout })[Symbol.asyncIterator]();
    const rpc = async (message) => {
      child.stdin.write(`${JSON.stringify(message)}\n`);
      const line = await lines.next();
      if (line.done) throw new Error('MCP server closed stdout');
      const reply = JSON.parse(line.value);
      if (reply.id !== message.id || reply.error) throw new Error('Unexpected MCP response');
      return reply.result;
    };
    try {
      await rpc({ jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: '2025-03-26', capabilities: {}, clientInfo: { name: 'test', version: '1' } } });
      child.stdin.write(`${JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' })}\n`);
      results.push(await rpc({ jsonrpc: '2.0', id: 2, method: 'tools/call', params: { name: 'public', arguments: {} } }));
    } finally {
      child.kill();
      await once(child, 'exit');
    }
  } else {
    const runtime = new URL('build/runtime/', pathToFileURL(`${process.argv[2]}/`));
    const { ToolExecutor } = await import(new URL('executor.js', runtime));
    const { toolRuntimeData } = await import(new URL('generated.js', runtime));
    const tool = { ...toolRuntimeData.public, execution: scenario.execution ?? {} };
    const executor = new ToolExecutor();
    for (let i = 0; i < (scenario.calls ?? 1); i++) results.push(await executor.execute('public', tool, {}));
  }
  await new Promise((resolve) => setTimeout(resolve, 20));
  console.log(JSON.stringify({ results, requests, closed, chunksSent }));
} finally {
  upstream.closeAllConnections();
  await new Promise((resolve) => upstream.close(resolve));
}
