#!/bin/bash

set -e

uv run ruff format
uv run pyright
if [ "$CI" = "true" ]; then
	uv run main.py "$@"
else
	uv run gui.py "$@"
fi
