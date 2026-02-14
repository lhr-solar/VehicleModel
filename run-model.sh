#!/bin/bash

set -e

uv run ruff format
uv run pyright
uv run gui.py "$@"
