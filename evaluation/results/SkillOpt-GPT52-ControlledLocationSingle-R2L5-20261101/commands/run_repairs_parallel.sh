#!/usr/bin/env bash
set -u -o pipefail
RUN="/Users/elsie/Desktop/SkillOpt-eva/experiments/gpt52-skillopt-controlled-location-single-r2l5-v2-20261027"
pids=()
for worker in 0 1 2 3; do
  "$RUN/commands/run_repair_worker.sh" "$worker" 4 &
  pids+=("$!")
done
failures=0
for pid in "${pids[@]}"; do
  wait "$pid" || failures=$((failures + 1))
done
exit "$failures"

