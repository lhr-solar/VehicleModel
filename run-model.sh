#!/bin/bash

set -e

uv run pyright
uv run main.py "$@"
