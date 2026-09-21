import assert from 'node:assert/strict';
import { once } from 'node:events';
import { pathToFileURL } from 'node:url';

const project = process.argv[2];
const { default: express } = await import(pathToFileURL(`${project}/node_modules/express/index.js`));
const { createReadiness, registerOperationalRoutes } = await import(
  pathToFileURL(`${project}/build/runtime/health.js`)
);
const app = express();
const readiness = createReadiness();
registerOperationalRoutes(app, readiness, () => true);
const listener = app.listen(0, '127.0.0.1');
await once(listener, 'listening');
const base = `http://127.0.0.1:${listener.address().port}`;

async function assertProbe(path, code, status) {
  const response = await fetch(base + path);
  assert.equal(response.status, code);
  assert.equal(response.headers.get('cache-control'), 'no-store');
  assert.deepEqual(await response.json(), { status });
}

try {
  await assertProbe('/healthz', 200, 'ok');
  await assertProbe('/readyz', 503, 'not_ready');
  readiness.markReady();
  await assertProbe('/readyz', 200, 'ready');
  readiness.markNotReady();
  await assertProbe('/readyz', 503, 'not_ready');
  await assertProbe('/healthz', 200, 'ok');
} finally {
  listener.close();
  listener.closeAllConnections();
  await once(listener, 'close');
}
