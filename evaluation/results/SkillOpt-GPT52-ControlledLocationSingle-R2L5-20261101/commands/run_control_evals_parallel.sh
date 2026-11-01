#!/usr/bin/env bash
set -u -o pipefail
RUN="/Users/elsie/Desktop/SkillOpt-eva/experiments/gpt52-skillopt-controlled-location-single-r2l5-v2-20261027"
workers="${CONTROL_WORKERS:-2}"
if (( workers < 1 || workers > 2 )); then
  echo "CONTROL_WORKERS must be 1 or 2" >&2
  exit 2
fi

pids=()
for ((worker = 0; worker < workers; worker++)); do
  "$RUN/commands/run_control_eval_worker.sh" "$worker" "$workers" &
  pids+=("$!")
done

status=0
for pid in "${pids[@]}"; do
  if ! wait "$pid"; then
    status=1
  fi
done
exit "$status"

