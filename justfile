set shell := ["bash", "-euo", "pipefail", "-c"]

default: help

help:
    @just --list

sync:
    ./scripts/workflow.sh sync

hooks-install:
    PRE_COMMIT_HOME=.pre-commit-cache uv run --no-sync pre-commit install --hook-type pre-commit --hook-type pre-push

hooks-run:
    PRE_COMMIT_HOME=.pre-commit-cache uv run --no-sync pre-commit run --all-files

hooks-run-push:
    PRE_COMMIT_HOME=.pre-commit-cache uv run --no-sync pre-commit run --all-files --hook-stage pre-push

format:
    uv run ruff format .

lint:
    uv run ruff check --fix .

test:
    uv run pytest --cov=openapi_to_mcp --cov-report=term-missing

docs-build:
    NO_MKDOCS_2_WARNING=1 uv run mkdocs build --strict

docs-serve:
    NO_MKDOCS_2_WARNING=1 uv run mkdocs serve

e2e-generated:
    ./scripts/e2e_generated_server.sh

e2e-cli:
    ./scripts/e2e_cli_matrix.sh

generate:
    ./scripts/workflow.sh generate

build:
    ./scripts/workflow.sh build-generated

run:
    ./scripts/workflow.sh run-generated

list:
    ./scripts/workflow.sh test-list

call tool args='{}':
    ./scripts/workflow.sh test-call "{{tool}}" '{{args}}'

smoke:
    ./scripts/workflow.sh smoke

clean:
    ./scripts/workflow.sh clean

clean-tmp:
    ./scripts/workflow.sh clean-tmp

clean-all:
    ./scripts/workflow.sh clean-all
