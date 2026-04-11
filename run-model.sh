#!/usr/bin/env bash
set -euo pipefail

MODE="run"        # run | check
RUN_CHECKS=1      # 1 = run ruff/pyright, 0 = skip
GUI=0

ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --check)      MODE="check"; shift ;;
    --run)        MODE="run"; shift ;;
    --no-checks)  RUN_CHECKS=0; shift ;;
    --gui)        GUI=1; shift ;;
    --)           shift; ARGS+=("$@"); break ;;
    *)            ARGS+=("$1"); shift ;;
  esac
done

# Env overrides
if [[ "${CHECK:-}" == "1" ]]; then
  MODE="check"
fi
if [[ "${NO_CHECKS:-}" == "1" ]]; then
  RUN_CHECKS=0
fi

echo "Mode: $MODE | Checks: $RUN_CHECKS"

run_checks() {
  if [[ "$RUN_CHECKS" -eq 0 ]]; then
    return 0
  fi

  if [[ "$MODE" == "check" ]]; then
    uv run ruff format --check .
    uv run pyright
  else
    uv run ruff format .
    uv run pyright
  fi
}

run_checks

if [[ "$MODE" == "run" ]]; then
  if [[ "$GUI" -eq 1 ]]; then
    uv run gui.py
  else
    uv run main.py "${ARGS[@]+"${ARGS[@]}"}"
  fi
fi
