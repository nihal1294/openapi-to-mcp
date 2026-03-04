set shell := ["bash", "-euo", "pipefail", "-c"]

default: help

help:
    @just --list

sync:
    ./scripts/workflow.sh sync

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

clean-all:
    ./scripts/workflow.sh clean-all
