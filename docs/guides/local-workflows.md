# Local Workflows

This page is for source checkout, development, and manual build or test flows.

It is not the primary end-user installation path.

## Clone and install for development

Development requires Python 3.14+, `uv`, Node.js 22+, `npm`, and Git.

```bash
git clone https://github.com/nihal1294/openapi-to-mcp.git
cd openapi-to-mcp
uv sync --dev
```

## Running CLI commands from a source checkout

Public docs assume an installed `openapi-to-mcp` binary.

From the repository root, either:

- prefix those commands with `uv run`, or
- use the `just` shortcuts documented below.

Example:

```bash
uv run openapi-to-mcp generate \
  --openapi-json ./openapi.yaml \
  --output-dir ./generated-server
```

## `just` shortcuts

```bash
just sync
just format
just lint
just test
just docs-build
just docs-serve
just e2e-generated
just e2e-cli
just generate
just build
just run
just list
just call getPetById '{"petId":1}'
just smoke
just clean
just clean-tmp
just clean-all
```

## `scripts/workflow.sh`

Get help:

```bash
scripts/workflow.sh help
```

Available commands:

- `sync`
- `generate`
- `build-generated`
- `run-generated`
- `test-list`
- `test-call <tool-name> [json-args]`
- `smoke`
- `clean`
- `clean-tmp`
- `clean-all`

## Workflow helper environment overrides

`scripts/workflow.sh` supports:

- `OPENAPI_JSON`
- `OUTPUT_DIR`
- `MCP_SERVER_NAME`
- `TRANSPORT`
- `HOST`
- `PORT`
- `MCP_ENDPOINT`
- `TARGET_API_BASE_URL`
- `UV_CACHE_DIR`

Example:

```bash
OUTPUT_DIR=/tmp/my-mcp \
TARGET_API_BASE_URL=https://petstore.swagger.io/v2 \
scripts/workflow.sh generate
```

## Recommended local verification order

```bash
just format
just lint
just test
just docs-build
just e2e-generated
just e2e-cli
```

## Hooks

Install hooks:

```bash
just hooks-install
```

Run them manually:

```bash
just hooks-run
just hooks-run-push
```

## CI and releases

The [repository workflows](https://github.com/nihal1294/openapi-to-mcp/tree/master/.github/workflows)
define CI checks, dependency review, documentation deployment, and releases.
GitHub shows the required checks and their results on each pull request.

Release behavior:

- releases are automated from `master`
- a release runs only when the version changes; a missing tag does not trigger
  rebuilding or republishing an unchanged version
- the release workflow validates the wheel and sdist, publishes them to PyPI,
  then creates the version tag and GitHub Release from those same artifacts

### PyPI publishing setup

The distribution name is `openapi-to-mcp-cli`; its command is `openapi-to-mcp`.
Before the first release, configure a [pending Trusted Publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)
in the maintainer's PyPI account with:

- PyPI project: `openapi-to-mcp-cli`
- GitHub owner: `nihal1294`
- Repository: `openapi-to-mcp`
- Workflow filename: `release.yml`
- Environment: `pypi`

Create the matching GitHub environment with deployments restricted to `master`.
Only the publish job can request the OIDC token; tests and builds run in a separate
job without publishing permissions. No long-lived PyPI token is required.

Choose a new version in `pyproject.toml`, update the changelog, and regenerate
`uv.lock` before merging a release. An existing version tag cannot be reused.
If publishing fails, check PyPI before retrying: a failed or interrupted upload
may have already published some files. If any files for that version are already
published, do not rerun `pypi-publish`; manually reconcile them against the original
build artifacts before continuing. Duplicate PyPI uploads fail instead of silently
replacing files. Never rebuild the same version to recover an upload.

If the PyPI job succeeded but GitHub release creation failed,
[rerun only the failed GitHub release job](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs#re-running-a-specific-job-in-a-workflow)
from the original workflow run. This reuses that run's commit and artifacts without
publishing to PyPI again. Do not rerun all jobs or push an unrelated commit to
repair a release. GitHub permits reruns for 30 days, and the build artifacts must
still be available.

A deleted tag or a release whose original run can no longer be retried requires
manual recovery from the published release's original commit and distributions.
Never retag a later commit or rebuild an already-published version to repair it.

Code scanning is expected through GitHub default CodeQL setup, not a workflow in the repo.
