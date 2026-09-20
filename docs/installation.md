# Installation

The Python distribution is [`openapi-to-mcp-cli`](https://pypi.org/project/openapi-to-mcp-cli/); the installed command is
`openapi-to-mcp`. Requires Python 3.14+. Running generated servers also requires
Node.js 22+ and npm.

## Install from PyPI

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) if needed,
then install the CLI in an isolated tool environment:

```bash
uv tool install openapi-to-mcp-cli
```

If the executable is not on your `PATH`, run:

```bash
uv tool update-shell
```

Then verify:

```bash
openapi-to-mcp --help
```

For one-off use without a persistent installation:

```bash
uvx --from openapi-to-mcp-cli openapi-to-mcp --help
```

## Upgrade

```bash
uv tool upgrade openapi-to-mcp-cli
```

If you installed an older Git-based distribution named `openapi-to-mcp`, remove it
before installing the renamed distribution so both do not claim the same command:

```bash
uv tool uninstall openapi-to-mcp
uv tool install openapi-to-mcp-cli
```

## Tagged Git install

To install directly from a specific GitHub release:

```bash
uv tool install git+https://github.com/nihal1294/openapi-to-mcp@vX.Y.Z
```

Replace `vX.Y.Z` with the release tag you want.

## GitHub Release artifacts

Each GitHub Release also publishes a wheel and source tarball.

These are the same distribution artifacts uploaded to PyPI and can also be used
for pinned manual installs.

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
