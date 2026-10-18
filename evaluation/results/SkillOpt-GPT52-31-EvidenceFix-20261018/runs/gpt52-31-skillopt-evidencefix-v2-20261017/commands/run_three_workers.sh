#!/usr/bin/env bash
set -u -o pipefail

RUN_DIR="/Users/elsie/Desktop/SkillOpt-eva/experiments/gpt52-31-skillopt-evidencefix-v2-20261017"

"$RUN_DIR/commands/run_worker.sh" 0 3 &
worker_one=$!
"$RUN_DIR/commands/run_worker.sh" 1 3 &
worker_two=$!
"$RUN_DIR/commands/run_worker.sh" 2 3 &
worker_three=$!

wait "$worker_one"; rc_one=$?
wait "$worker_two"; rc_two=$?
wait "$worker_three"; rc_three=$?

printf 'worker_exit_codes=%s,%s,%s\n' "$rc_one" "$rc_two" "$rc_three"
if (( rc_one != 0 || rc_two != 0 || rc_three != 0 )); then
  exit 1
fi
