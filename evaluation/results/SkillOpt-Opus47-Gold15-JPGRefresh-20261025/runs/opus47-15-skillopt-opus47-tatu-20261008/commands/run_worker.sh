#!/usr/bin/env bash
set -u -o pipefail

RUN_ID="opus47-15-skillopt-opus47-tatu-20261008"
ROOT="/Users/elsie/Desktop/SkillOpt-eva"
RUN_DIR="$ROOT/experiments/$RUN_ID"
WORKER_INDEX="${1:?usage: run_worker.sh WORKER_INDEX WORKER_COUNT}"
WORKER_COUNT="${2:?usage: run_worker.sh WORKER_INDEX WORKER_COUNT}"
source "$RUN_DIR/commands/env.sh"

if (( WORKER_INDEX < 0 || WORKER_INDEX >= WORKER_COUNT )); then
  echo "worker index must be in [0, worker count)" >&2
  exit 2
fi

LOG="$RUN_DIR/logs/terminal-$((WORKER_INDEX + 1)).log"
mkdir -p "$RUN_DIR/logs"
failures=0
index=0
while IFS= read -r task || [[ -n "$task" ]]; do
  [[ -z "$task" || "$task" == \#* ]] && continue
  if [[ -f "$RUN_DIR/STOP_AFTER_CURRENT" ]]; then
    printf '[%s] worker=%s stop requested before next task\n' "$(date -u +%FT%TZ)" "$WORKER_INDEX" | tee -a "$LOG"
    break
  fi
  if (( index % WORKER_COUNT == WORKER_INDEX )); then
    printf '[%s] worker=%s task=%s start\n' "$(date -u +%FT%TZ)" "$WORKER_INDEX" "$task" | tee -a "$LOG"
    if /opt/homebrew/bin/uv run --project "$ROOT/skill-repair-benchmark" --locked \
      python "$ROOT/scripts/run_method.py" --run-id "$RUN_ID" --method skillopt --task "$task" \
      2>&1 | tee -a "$LOG"; then
      if ! /opt/homebrew/bin/uv run --project "$ROOT/skill-repair-benchmark" --locked \
        python "$ROOT/scripts/validate_skillopt_task.py" --run-id "$RUN_ID" --task "$task" \
        2>&1 | tee -a "$LOG"; then
        failures=$((failures + 1))
      fi
    else
      failures=$((failures + 1))
    fi
    printf '[%s] worker=%s task=%s end failures=%s\n' "$(date -u +%FT%TZ)" "$WORKER_INDEX" "$task" "$failures" | tee -a "$LOG"
    if [[ -f "$RUN_DIR/STOP_AFTER_CURRENT" ]]; then
      printf '[%s] worker=%s stop requested after current task\n' "$(date -u +%FT%TZ)" "$WORKER_INDEX" | tee -a "$LOG"
      break
    fi
  fi
  index=$((index + 1))
done < "$RUN_DIR/tasks.txt"

exit "$failures"
