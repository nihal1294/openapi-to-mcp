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
TARGET_API_BASE_URL=https://petstore3.swagger.io/api/v3 \
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

- Release Please maintains one rolling release PR from `master`. A human review
  and merge of that PR authorizes its build, PyPI publication, tag, and GitHub
  Release; there is no additional publish approval.
- release runs are serialized with up to 100 pending runs queued, so later pushes
  do not replace a pending release finalization; additional runs are canceled if
  the queue is full
- the release workflow validates the wheel and sdist, then publishes, tags, and
  creates the GitHub Release from those same artifacts

### Release intent and evidence

Use strict semantic pull request titles:

- `fix:` or `perf:` for compatible fixes
- `fix(deps):` for runtime dependency updates
- `feat:` for backward-compatible features
- `feat!:` or `fix!:` for breaking changes, with a `Migration:` note in the
  pull request body
- `chore:`, `docs:`, `test:`, and `ci:` for changes that do not release the
  product; Dependabot uses `chore(deps-dev):` for development dependencies

Before 1.0, compatible fixes are patches and features or breaking changes are
minor releases. Promotion to 1.0 is an explicit maintainer decision. Do not add
`Release-As:` to ordinary pull requests: it cannot force a version.

Documentation changes appear under **Documentation** in the next product
release's changelog, including guides and deployment examples. They do not
start a release by themselves or increase the version bump selected for the
product changes. The release preflight requires a releasable product change
before creating or updating the rolling release proposal.

The release check compares a bounded fixed corpus of CLI, generated-server,
custom-tool preservation, and MCP wire behavior. Passing it demonstrates those
tested contracts only. Missing or conflicting evidence fails the check instead
of being classified as compatible.

For a legacy runtime change that reached `master` without a semantic title,
add a reviewed native Release Please override to the merged pull request body:

```text
BEGIN_COMMIT_OVERRIDE
fix(deps): describe the compatible runtime dependency update
END_COMMIT_OVERRIDE
```

Use overrides to correct the effective commit classification, never to force a
version. They are designed for squash merges and should include a clear reason
in the pull request discussion.

### Release automation activation

Release Please uses the built-in GitHub token to create or update its release
PR. The repository owner must enable GitHub's **Allow GitHub Actions to create
and approve pull requests** setting before activation. This repository has not
enabled that setting as part of this change, and the workflow never approves or
merges a pull request.

If the proposal job is denied permission to create a pull request, the
repository owner must enable that checkbox; workflow credentials cannot enable
it.

GitHub may require a maintainer to select **Approve workflows to run** for CI
on a release PR created with the built-in token. That approves CI execution; it
does not authorize publication. See [GitHub's workflow trigger
behavior](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).

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

Release Please synchronizes version metadata, the changelog, and the root project
version in `uv.lock`. An existing version tag cannot be reused.

An `autorelease: pending` label means a merged release is unfinished and blocks
another release proposal. The finalizer changes it to `autorelease: tagged` only
after it verifies the original PyPI and GitHub release artifact hashes. If only
that finalization step fails, retry the finalizer after it verifies the completed
publication. Do not rerun all jobs, rebuild, reupload, retag a later commit, or
use replacement artifacts to recover a release.

Code scanning is expected through GitHub default CodeQL setup, not a workflow in the repo.
