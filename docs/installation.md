# Installation

Treat `openapi-to-mcp` as a standalone CLI first.

## Preferred install path today

Because the project is not yet published to PyPI, the cleanest end-user path today is a tagged Git install with `uv tool install`.

```bash
uv tool install git+https://github.com/nihal1294/openapi-to-mcp@vX.Y.Z
```

Replace `vX.Y.Z` with the release tag you want.

If the executable is not on your `PATH`, run:

```bash
uv tool update-shell
```

Then verify:

```bash
openapi-to-mcp --help
```

## Why this is the preferred user path

- it installs the CLI as an isolated tool,
- it avoids mixing project and development dependencies into your shell,
- it keeps the public docs aligned with the installable CLI experience.

## GitHub Release artifacts

Each GitHub Release also publishes a wheel and source tarball.

Treat those artifacts as the canonical release outputs for packaging and pinned manual installs. The public docs still prefer `uv tool install` from a tagged release because it is the simplest end-user flow until PyPI publishing exists.

## Source checkout and development install

Use this only when you are developing on the project itself.

```bash
git clone https://github.com/nihal1294/openapi-to-mcp.git
cd openapi-to-mcp
uv sync --dev
```

This is the correct path for:

- contributing,
- running tests,
- building docs,
- editing generator or runtime code.

For the full source workflow, see [Local Workflows](guides/local-workflows.md).
