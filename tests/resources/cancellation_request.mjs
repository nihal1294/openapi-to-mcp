import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { once } from 'node:events';
import { pathToFileURL } from 'node:url';

let requests = 0;
let closed = 0;
let notifyRequest;
let requestSeen = new Promise((resolve) => { notifyRequest = resolve; });
let mode = 'hold';
let retryController;
let retryAttempts = 0;
const upstream = createServer((req, res) => {
  requests++;
  res.on('close', () => { if (!res.writableEnded) closed++; });
  notifyRequest();
  if (mode === 'hold') return;
  if (mode === 'fail') { res.writeHead(503).end(); return; }
  if (mode === 'retry') {
    retryAttempts++;
    if (retryAttempts === 1) res.writeHead(503).end();
    else { retryController.abort(); res.writeHead(503).end(); }
  } else res.writeHead(200, { 'content-type': 'application/json' }).end('{"ok":true}');
});
upstream.listen(0, '127.0.0.1');
await once(upstream, 'listening');
try {
  Object.assign(process.env, {
    TARGET_API_BASE_URL: `http://127.0.0.1:${upstream.address().port}`,
    MCP_MAX_CONCURRENCY: '2', MCP_PER_TOOL_MAX_CONCURRENCY: '1',
    MCP_CACHE_TTL_MS: '10000', MCP_RETRY_MAX_RETRIES: '2',
    MCP_RETRY_BUDGET_PER_MINUTE: '10', MCP_CIRCUIT_BREAKER_FAILURE_THRESHOLD: '1',
  });
  const runtime = new URL('build/runtime/', pathToFileURL(`${process.argv[2]}/`));
  const { ToolExecutor } = await import(new URL('executor.js', runtime));
  const { ToolCircuitBreaker } = await import(new URL('circuit_breaker.js', runtime));
  const breaker = new ToolCircuitBreaker();
  const settings = { failureThreshold: 1, cooldownMs: 0 };
  breaker.recordFailure('probe', settings, breaker.acquireExecution('probe', settings));
  const probe = breaker.acquireExecution('probe', settings);
  assert.equal(probe.halfOpen, true);
  breaker.cancelExecution('probe', probe);
  assert.equal(breaker.acquireExecution('probe', settings).halfOpen, true);
  const { toolRuntimeData } = await import(new URL('generated.js', runtime));
  const executor = new ToolExecutor();
  const tool = toolRuntimeData.public;
  const call = (controller, args = {}) => executor.execute('public', tool, args, controller.signal);
  const pre = new AbortController(); pre.abort();
  assert.equal((await call(pre))._meta.error.code, 'request_cancelled');
  assert.equal(requests, 0);
  const active = new AbortController();
  const first = call(active);
  await requestSeen;
  const queued = new AbortController();
  const second = call(queued);
  const global = new AbortController();
  const third = call(global);
  await new Promise((resolve) => setTimeout(resolve, 30));
  queued.abort(); global.abort();
  assert.equal((await second)._meta.error.code, 'request_cancelled');
  assert.equal((await third)._meta.error.code, 'request_cancelled');
  active.abort();
  assert.equal((await first)._meta.error.code, 'request_cancelled');
  await new Promise((resolve) => setTimeout(resolve, 50));
  assert.equal(requests, 1);
  assert.equal(closed, 1);
  mode = 'retry'; retryController = new AbortController();
  assert.equal((await call(retryController))._meta.error.code, 'request_cancelled');
  assert.equal(retryAttempts, 2);
  assert.equal(requests, 3);
  mode = 'success';
  const good = await call(new AbortController());
  assert.equal(good.structuredContent.ok, true);
  assert.equal(requests, 4);
  const cached = await call(new AbortController());
  assert.equal(cached.structuredContent.ok, true);
  assert.equal(requests, 4);
  // A real cancelled half-open probe must leave the lease available.
  const probeExecutor = new ToolExecutor();
  const probeTool = { ...tool, execution: { cacheTtlMs: 0, retryMaxRetries: 0, circuitBreakerFailureThreshold: 1, circuitBreakerCooldownMs: 20 } };
  mode = 'fail';
  assert.equal((await probeExecutor.execute('public', probeTool, {}))._meta.error.code, 'api_server_error');
  await new Promise((resolve) => setTimeout(resolve, 30));
  mode = 'hold';
  requestSeen = new Promise((resolve) => { notifyRequest = resolve; });
  const probeController = new AbortController();
  const probeCall = probeExecutor.execute('public', probeTool, {}, probeController.signal);
  await requestSeen;
  probeController.abort();
  assert.equal((await probeCall)._meta.error.code, 'request_cancelled');
  mode = 'success';
  assert.equal((await probeExecutor.execute('public', probeTool, {})).structuredContent.ok, true);

  // Delay adapter rejection after abort so the order is explicit, independent
  // of event-loop scheduling or a real network adapter's rejection timing.
  for (const firstCause of ['timeout', 'caller', 'upstream']) {
    const raceExecutor = new ToolExecutor();
    const controller = new AbortController();
    let attempts = 0;
    let abortObserved;
    const observed = new Promise((resolve) => { abortObserved = resolve; });
    let rejectRequest;
    let requestStarted;
    const started = new Promise((resolve) => { requestStarted = resolve; });
    raceExecutor.axiosInstance.defaults.adapter = ({ signal }) => {
      attempts++;
      requestStarted();
      return new Promise((resolve, reject) => {
        rejectRequest = reject;
        signal.addEventListener('abort', abortObserved, { once: true });
      });
    };
    const raceTool = { ...tool, execution: { cacheTtlMs: 0, timeoutMs: 15, retryMaxRetries: 2, retryBudgetPerMinute: 10, circuitBreakerFailureThreshold: 1, circuitBreakerCooldownMs: 10000 } };
    const result = raceExecutor.execute('public', raceTool, {}, controller.signal);
    await started;
    if (firstCause === 'timeout') {
      await observed;
      controller.abort();
      rejectRequest({ __CANCEL__: true });
    } else if (firstCause === 'caller') {
      controller.abort();
      await observed;
      await new Promise((resolve) => setTimeout(resolve, 30));
      rejectRequest({ __CANCEL__: true });
    } else {
      rejectRequest({ isAxiosError: true, response: { status: 503, data: {}, headers: {} }, message: 'failed' });
      controller.abort();
    }
    const outcome = await result;
    assert.equal(outcome._meta.error.code, firstCause === 'timeout' ? 'tool_timeout' : firstCause === 'caller' ? 'request_cancelled' : 'api_server_error');
    assert.equal(attempts, 1);
    // Timeout/upstream failure counts toward the breaker; caller cancellation does not.
    if (firstCause !== 'caller') {
      assert.equal((await raceExecutor.execute('public', raceTool, {}))._meta.error.code, 'circuit_breaker_open');
      assert.equal(attempts, 1);
    }
  }
  console.log('cancellation checks passed');
} finally {
  upstream.closeAllConnections();
  await new Promise((resolve) => upstream.close(resolve));
}
