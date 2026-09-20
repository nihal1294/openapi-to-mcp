import { createServer } from 'node:http';

const apiKey = process.env.EXAMPLE_API_KEY;
if (!apiKey) throw new Error('EXAMPLE_API_KEY is required');

createServer((request, response) => {
  response.setHeader('Content-Type', 'application/json');
  if (request.method === 'GET' && request.url === '/health') {
    response.end(JSON.stringify({ status: 'ok' }));
    return;
  }
  if (request.headers['x-api-key'] !== apiKey) {
    response.writeHead(401).end(JSON.stringify({ error: 'Invalid API key' }));
    return;
  }
  const match = request.url?.match(/^\/widgets\/([^/?]+)$/);
  if (request.method !== 'GET' || !match) {
    response.writeHead(404).end(JSON.stringify({ error: 'Not found' }));
    return;
  }
  response.end(JSON.stringify({ id: decodeURIComponent(match[1]), source: 'compose-mock' }));
}).listen(8081, '0.0.0.0');
