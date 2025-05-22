# Usage Examples

This section provides step-by-step examples to help you use `openapi-to-mcp` effectively. It covers:
- Example OpenAPI v3 input specs (JSON and YAML)
- The CLI command to generate a Node.js/TypeScript MCP server
- The structure and contents of the generated output
- Before/after code samples to illustrate the transformation
- Explanations for each step

---

## 1. Example OpenAPI v3 Input Specs

### Example: Simple Pet API (JSON)

**`pet-api.json`:**
```json
{
  "openapi": "3.0.3",
  "info": {
    "title": "Simple Pet API",
    "version": "1.0.0"
  },
  "paths": {
    "/pet/{petId}": {
      "get": {
        "summary": "Get a pet by ID",
        "operationId": "getPetById",
        "parameters": [
          {
            "name": "petId",
            "in": "path",
            "required": true,
            "schema": { "type": "integer" }
          }
        ],
        "responses": {
          "200": {
            "description": "A pet object.",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "id": { "type": "integer" },
                    "name": { "type": "string" }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

### Example: Simple Pet API (YAML)

**`pet-api.yaml`:**
```yaml
openapi: 3.0.3
info:
  title: Simple Pet API
  version: 1.0.0
paths:
  /pet/{petId}:
    get:
      summary: Get a pet by ID
      operationId: getPetById
      parameters:
        - name: petId
          in: path
          required: true
          schema:
            type: integer
      responses:
        '200':
          description: A pet object.
          content:
            application/json:
              schema:
                type: object
                properties:
                  id:
                    type: integer
                  name:
                    type: string
```

---

## 2. Generate an MCP Server from the OpenAPI Spec

Run the following command to generate a Node.js/TypeScript MCP server from your OpenAPI spec (replace the file name as needed):

```bash
poetry run openapi-to-mcp generate \
  --openapi-json pet-api.json \
  --output-dir ./generated-pet-mcp \
  --mcp-server-name pet-mcp-server \
  --transport stdio
```

**What this does:**
- Reads your OpenAPI spec (`pet-api.json` or `pet-api.yaml`)
- Generates a new MCP server project in `./generated-pet-mcp`
- Sets up the server to use STDIO transport

---

## 3. Structure of the Generated Output

After running the command, your output directory will look like this:

```
generated-pet-mcp/
├── README.md
├── package.json
├── tsconfig.json
├── .env.example
├── src/
│   ├── index.ts
│   ├── server.ts
│   ├── transport_stdio.ts
│   └── ...
```

### Sample Generated Code: `src/index.ts`

```typescript
import { createServer } from './server';

createServer();
```

### Sample Generated Code: `src/server.ts` (snippet)

```typescript
// ...existing code...
export const tools = [
  {
    name: 'getPetById',
    description: 'Get a pet by ID',
    inputSchema: {
      type: 'object',
      properties: {
        petId: { type: 'integer' }
      },
      required: ['petId']
    },
    // ...handler code...
  }
];
// ...existing code...
```

---

## 4. Before/After: What You Provide vs. What You Get

### Before: Your OpenAPI Spec (YAML)
```yaml
paths:
  /pet/{petId}:
    get:
      operationId: getPetById
      parameters:
        - name: petId
          in: path
          required: true
          schema:
            type: integer
```

### After: Generated MCP Tool (TypeScript)
```typescript
{
  name: 'getPetById',
  inputSchema: {
    type: 'object',
    properties: {
      petId: { type: 'integer' }
    },
    required: ['petId']
  },
  // ...handler code...
}
```

---

## 5. Step-by-Step Explanation

1. **Prepare your OpenAPI v3 spec** (JSON or YAML). See above for examples.
2. **Run the CLI command** (see above) to generate the MCP server.
3. **Navigate to the output directory**:
   ```bash
   cd generated-pet-mcp
   ```
4. **Copy `.env.example` to `.env`** and set `TARGET_API_BASE_URL` to your API's base URL.
5. **Install dependencies and build the server**:
   ```bash
   npm install
   npm run build
   npm start
   ```
6. **Test your server** using the `test-server` command or the MCP Inspector.

---

These examples should help you get started quickly with `openapi-to-mcp`!
