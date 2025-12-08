#!/bin/bash
uv run pyright
uv run main.py "$@"
