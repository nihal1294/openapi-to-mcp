import { createServer } from 'node:http';
import { once } from 'node:events';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const scenario = JSON.parse(readFileSync(0, 'utf8'));
const requests = [];
const upstream = createServer((req, res) => {
  requests.push({ path: req.url, headers: req.headers });
  res.writeHead(scenario.status ?? 200, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(scenario.status === 401 ? { message: 'Unauthorized' } : { ok: true }));
});
upstream.listen(0, '127.0.0.1');
await once(upstream, 'listening');
try {
  Object.assign(process.env, scenario.env, {
    TARGET_API_BASE_URL: `http://127.0.0.1:${upstream.address().port}`,
    MCP_AUDIT_MODE: 'logs',
  });
  const runtime = new URL('build/runtime/', pathToFileURL(`${process.argv[2]}/`));
  const { ToolExecutor } = await import(new URL('executor.js', runtime));
  const { toolRuntimeData } = await import(new URL('generated.js', runtime));
  const name = scenario.tool ?? 'inherited';
  const tool = { ...toolRuntimeData[name], ...scenario.metadata };
  const result = await new ToolExecutor().execute(name, tool, scenario.arguments ?? {});
  console.log(JSON.stringify({ result, requests }));
} finally {
  upstream.closeAllConnections();
  await new Promise((resolve) => upstream.close(resolve));
}
