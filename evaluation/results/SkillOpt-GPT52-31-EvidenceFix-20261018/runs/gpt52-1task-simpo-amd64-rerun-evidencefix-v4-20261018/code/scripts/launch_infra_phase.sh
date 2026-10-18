#!/bin/bash
# Launch infra parallel_phase for one arm. Assumes queue already prepared and machine idle.
set -euo pipefail
cd /Users/elsie/Desktop/SkillOpt-eva

RUN_ID="${1:?run_id}"
N="${2:?n}"
L="${3:?L}"
R="${4:?R}"
WORKERS="${5:-5}"

# Refuse if continue or this run already has workers
if ps aux | grep -v grep | grep -q 'continue_non_infra.py'; then
  echo "REFUSE: continue_non_infra still running" >&2
  exit 2
fi
if ps aux | grep -v grep | grep -E "parallel_phase.py --run-id ${RUN_ID}|run_method.py --run-id ${RUN_ID}" >/dev/null; then
  echo "REFUSE: workers already running for ${RUN_ID}" >&2
  exit 3
fi

if ! docker info >/dev/null 2>&1; then
  open -a Docker || true
  for i in $(seq 1 60); do
    docker info >/dev/null 2>&1 && break
    sleep 3
  done
fi

set -a
# shellcheck disable=SC1091
source .env
set +a
export PATH="/opt/homebrew/opt/python@3.12/libexec/bin:/opt/homebrew/bin:$PATH"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/private/tmp/skillopt-eva-uv-cache}"
export PYTHONUNBUFFERED=1
export SKILLOPT_EVA_DIAGNOSIS_N="$N"
export SKILLOPT_EVA_EDIT_BUDGET_L="$L"
export SKILLOPT_EVA_REPAIR_ROUNDS_R="$R"
unset SKILLOPT_EVA_SMOKE DEBUG || true

mkdir -p "experiments/${RUN_ID}/logs"
LOG="experiments/${RUN_ID}/logs/infra_rerun_phase.log"
echo "$(date '+%Y-%m-%d %H:%M:%S') launch ${RUN_ID} n=${N} L=${L} R=${R} workers=${WORKERS}" \
  >> experiments/liveboards/gpt52-hyperparam-suite/infra_rerun.log

nohup /opt/homebrew/bin/python3.12 -u scripts/parallel_phase.py \
  --run-id "$RUN_ID" --phase skillopt --workers "$WORKERS" \
  >> "$LOG" 2>&1 &
echo "pid=$!"
sleep 3
tail -15 "$LOG"
