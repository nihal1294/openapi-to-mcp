set shell := ["bash", "-euo", "pipefail", "-c"]

default: help

help:
    @just --list

sync:
    ./scripts/workflow.sh sync

test:
    uv run pytest --cov=openapi_to_mcp --cov-report=term-missing

e2e-generated:
    ./scripts/e2e_generated_server.sh

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
