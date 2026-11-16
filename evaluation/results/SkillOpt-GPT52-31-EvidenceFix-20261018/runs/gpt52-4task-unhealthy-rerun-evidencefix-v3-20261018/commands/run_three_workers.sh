#!/usr/bin/env bash
set -u -o pipefail

RUN_DIR="/Users/elsie/Desktop/SkillOpt-eva/experiments/gpt52-4task-unhealthy-rerun-evidencefix-v3-20261018"
pids=()
for worker in 0 1 2; do
  bash "$RUN_DIR/commands/run_worker.sh" "$worker" 3 &
  pids+=("$!")
done

codes=()
overall=0
for pid in "${pids[@]}"; do
  if wait "$pid"; then
    codes+=(0)
  else
    code=$?
    codes+=("$code")
    overall=1
  fi
done
printf 'rerun_worker_exit_codes=%s\n' "$(IFS=,; echo "${codes[*]}")"
exit "$overall"
