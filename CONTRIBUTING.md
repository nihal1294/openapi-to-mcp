# Contributing

This project treats `openapi-to-mcp` as a standalone CLI product, with the repository used for development, testing, and release automation.

## Prerequisites

You need:

- Python 3.14+
- `uv`
- Node.js 20+
- `npm`
- Git

## Development setup

```bash
git clone https://github.com/nihal1294/openapi-to-mcp.git
cd openapi-to-mcp
uv sync --dev
```

Optional but recommended:

```bash
just hooks-install
```

## Repository workflows

Common commands:

```bash
just format
just lint
just test
just docs-build
just e2e-generated
just e2e-cli
```

Equivalent direct commands are available, but `just` is the intended contributor shortcut layer.

## What to update when you change behavior

- Python code: add or update behavior-focused tests in `tests/`
- CLI behavior or options: update help text and docs under `docs/`
- Public usage flows: update the public docs site pages under `docs/`
- Contributor-only flows: update [docs/guides/local-workflows.md](docs/guides/local-workflows.md)
- Release-visible changes: update `CHANGELOG.md` and version metadata when appropriate

`README.md` is intentionally lean. Detailed user-facing documentation belongs in `docs/`, not in the README.

## Documentation model

- Public product docs: `docs/`
- Contributor and source-checkout workflows: [docs/guides/local-workflows.md](docs/guides/local-workflows.md)
- MkDocs config: `mkdocs.yml`

Build docs locally with:

```bash
just docs-build
```

## Testing expectations

Before opening a PR, run at least:

```bash
just format
just lint
just test
just docs-build
```

Run these when your change affects generation or runtime behavior:

```bash
just e2e-generated
just e2e-cli
```

Testing standard:

- test behavior changes, not just code paths
- add regression coverage for every real fix
- avoid vanity tests that only increase coverage numbers

## Pull requests

Each pull request should:

- address one coherent change
- explain what changed and why
- include docs updates when user-facing behavior changes
- include tests when behavior changes
- pass the required GitHub checks on `master`

Required checks currently include:

- `quality-py314`
- `e2e-generated-server (node-20)`
- `e2e-generated-server (node-22)`
- `e2e-cli-matrix`
- `dependency-review`

## Code standards

Follow the committed repository standards and keep changes small, typed, and easy to reason about.

In practice, that means:

- small, focused files and functions
- explicit type hints
- docstrings for public APIs
- no unnecessary complexity
- no vanity abstractions

## Branching and releases

- open PRs against `master`
- keep version bumps intentional
- GitHub Releases are automated from `master` when the version changes or the version tag is missing

## Reporting bugs or requesting features

When opening an issue, include:

- the exact command you ran
- the OpenAPI input shape or a minimal reproducer
- expected behavior vs actual behavior
- relevant logs or generated output
- your Python and Node versions

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0. See [LICENSE](LICENSE).
