import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const input = JSON.parse(readFileSync(0, 'utf8'));
const root = new URL('build/runtime/', pathToFileURL(`${process.argv[2]}/`));
const { ToolExecutor } = await import(new URL('executor.js', root));
const { toolRuntimeData } = await import(new URL('generated.js', root));
const executor = new ToolExecutor();
const results = [];
for (const call of input) {
  if (call.token !== undefined) process.env.AUTH_KEY_API_KEY = call.token;
  Object.assign(process.env, call.env ?? {});
  results.push(await executor.execute(call.tool, toolRuntimeData[call.tool], call.args));
}
process.stdout.write(JSON.stringify(results));
