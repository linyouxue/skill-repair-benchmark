#!/usr/bin/env bash
set -u

ROOT="/Users/elsie/Desktop/SkillOpt-eva/experiments"
WORKER_INDEX="${1:?usage: run_worker.sh WORKER_INDEX WORKER_COUNT}"
WORKER_COUNT="${2:?usage: run_worker.sh WORKER_INDEX WORKER_COUNT}"
failures=0

/bin/bash "$ROOT/gpt52-31-skillopt-gpt52-ai360-20261011/commands/run_worker.sh" \
  "$WORKER_INDEX" "$WORKER_COUNT" || failures=$((failures + 1))
/bin/bash "$ROOT/opus47-15-skillopt-opus47-tatu-20261008/commands/run_worker.sh" \
  "$WORKER_INDEX" "$WORKER_COUNT" || failures=$((failures + 1))

exit "$failures"
