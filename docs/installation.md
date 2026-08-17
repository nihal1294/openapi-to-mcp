# Installation

Treat `openapi-to-mcp` as a standalone CLI first.

## Install from PyPI

New releases are published to PyPI.

Run the CLI without a permanent install:

```bash
uvx openapi-to-mcp --help
```

Install it permanently:

```bash
uv tool install openapi-to-mcp
# or
pip install openapi-to-mcp
openapi-to-mcp --help
```

## Tagged Git fallback

If a specific release is not yet available on PyPI, use a tagged Git install instead:

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

## Why the PyPI path is preferred

- it keeps installation on the standard Python packaging path,
- it works with both `uv` and `pip`,
- it keeps source-checkout workflows separate from end-user installs.

## GitHub Release artifacts

Each GitHub Release also publishes a wheel and source tarball.

Treat those artifacts as the canonical build outputs for packaging verification and
pinned manual installs. They are no longer the default user path.

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
