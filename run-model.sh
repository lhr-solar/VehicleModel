#!/bin/bash
set -euo pipefail

uv run ruff format . --exclude "extern/*"
uv run pyright
uv run main.py "$@"
