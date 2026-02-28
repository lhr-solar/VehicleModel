#!/bin/bash
set -euo pipefail

uv run ruff format
uv run pyright
uv run main.py "$@"
