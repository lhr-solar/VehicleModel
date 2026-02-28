#!/bin/bash

set -e

uv run ruff format
uv run pyright
if [[ "$1" == "--gui" ]]; then
	shift
	uv run gui.py 
else
	uv run main.py "$@"
fi
