#!/bin/bash
set -euo pipefail

uv run ruff format
uv run pyright
if [[ "$1" == "--gui" ]]; then
	shift
	uv run gui.py "$@"
else
	uv run main.py "$@"
fi
