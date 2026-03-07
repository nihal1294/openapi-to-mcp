# Troubleshooting

## `TARGET_API_BASE_URL is unresolved`

The generated runtime could not resolve a real base URL.

Fix one of:

1. pass `--target-api-base-url`
2. pass `--env-source`
3. ensure the spec contains a usable server URL
4. set `TARGET_API_BASE_URL` in the environment

## `--env-source` fails to parse

Check whether the value is one of:

- a valid JSON object string,
- a real `.json` file path,
- a real `.env` file path.

## `npm start` fails in a generated project

Check:

1. `.env` exists
2. `TARGET_API_BASE_URL` is real, not placeholder text
3. `npm install` and `npm run build` already succeeded
4. the generated project has a usable Node runtime available

## `test-server` usage error

Common causes:

- missing `--transport`
- missing `--server-cmd` for `stdio`
- invalid `--mcp-endpoint`
- `--tool-args` without `--tool-name`
- neither `--list-tools` nor `--tool-name`

## `just e2e-generated` fails

Use:

```bash
KEEP_TMP=1 just e2e-generated
```

Then inspect the preserved logs in the temp directory.

## `just e2e-cli` fails

Use:

```bash
KEEP_TMP=1 just e2e-cli
```

Then inspect the preserved command output and generated temp directories.

## Docs build fails

Run:

```bash
just docs-build
```

Typical causes:

- broken Markdown links
- pages added under `docs/` but not wired into `mkdocs.yml`

## Release workflow fails

Check:

1. the package version in `pyproject.toml`
2. whether the matching tag already points at a different commit
3. whether `uv build` produces both a wheel and a source tarball locally
