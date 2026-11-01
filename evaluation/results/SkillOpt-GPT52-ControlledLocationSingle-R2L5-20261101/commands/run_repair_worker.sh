#!/usr/bin/env bash
set -u -o pipefail
ROOT="/Users/elsie/Desktop/SkillOpt-eva"
RUN="$ROOT/experiments/gpt52-skillopt-controlled-location-single-r2l5-v2-20261027"
RUNNER="$ROOT/skill-repair-controlled-datasets-20261020/tools/runner.py"
ADAPTER="$RUN/commands/skillopt_controlled_adapter.py"
PYTHON="$ROOT/skill-repair-benchmark/.venv/bin/python"
worker="${1:?worker index required}"
workers="${2:?worker count required}"
source "$RUN/commands/env.sh"
mkdir -p "$RUN/terminal_logs"
log="$RUN/terminal_logs/repair-worker-$worker.log"
index=0
failures=0
while IFS= read -r trial || [[ -n "$trial" ]]; do
  [[ -z "$trial" || "$trial" == \#* ]] && continue
  if (( index % workers == worker )); then
    dataset="${trial%%-*}"
    input="$RUN/inputs/$dataset/$trial"
    trial_root="$RUN/candidates/$dataset/$trial"
    complete="$(find "$trial_root" -maxdepth 2 -name CANDIDATE_SHA256.json -print -quit 2>/dev/null || true)"
    if [[ -n "$complete" ]]; then
      printf '[%s] skip-complete %s\n' "$(date -u +%FT%TZ)" "$trial" | tee -a "$log"
      index=$((index + 1))
      continue
    fi
    attempt=1
    while [[ -e "$trial_root/attempt-$(printf '%03d' "$attempt")" ]]; do
      attempt=$((attempt + 1))
    done
    output="$trial_root/attempt-$(printf '%03d' "$attempt")"
    printf '[%s] start %s\n' "$(date -u +%FT%TZ)" "$trial" | tee -a "$log"
    if python3 -B "$RUNNER" repair --input "$input" --out "$output" --adapter "$PYTHON" "$ADAPTER" 2>&1 | tee -a "$log"; then
      printf '[%s] complete %s\n' "$(date -u +%FT%TZ)" "$trial" | tee -a "$log"
    else
      failures=$((failures + 1))
      printf '[%s] failed %s\n' "$(date -u +%FT%TZ)" "$trial" | tee -a "$log"
    fi
  fi
  index=$((index + 1))
done < "$RUN/configs/trials.txt"
exit "$failures"

