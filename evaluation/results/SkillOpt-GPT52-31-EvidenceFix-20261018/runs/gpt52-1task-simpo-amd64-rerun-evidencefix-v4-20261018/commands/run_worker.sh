#!/usr/bin/env bash
set -u -o pipefail

RUN_ID="gpt52-1task-simpo-amd64-rerun-evidencefix-v4-20261018"
ROOT="/Users/elsie/Desktop/SkillOpt-eva"
RUN_DIR="$ROOT/experiments/$RUN_ID"
LOG="$RUN_DIR/logs/rerun-terminal-1.log"
source "$RUN_DIR/commands/env.sh"

printf '[%s] worker=0 task=simpo-code-reproduction start platform=linux/amd64\n' "$(date -u +%FT%TZ)" | tee -a "$LOG"
if /opt/homebrew/bin/uv run --project "$ROOT/skill-repair-benchmark" --locked \
  python "$ROOT/scripts/run_method.py" --run-id "$RUN_ID" --method skillopt --task simpo-code-reproduction \
  2>&1 | tee -a "$LOG"; then
  /opt/homebrew/bin/uv run --project "$ROOT/skill-repair-benchmark" --locked \
    python "$ROOT/scripts/validate_skillopt_task.py" --run-id "$RUN_ID" --task simpo-code-reproduction \
    2>&1 | tee -a "$LOG"
  status=$?
else
  status=$?
fi
printf '[%s] worker=0 task=simpo-code-reproduction end status=%s\n' "$(date -u +%FT%TZ)" "$status" | tee -a "$LOG"
exit "$status"
