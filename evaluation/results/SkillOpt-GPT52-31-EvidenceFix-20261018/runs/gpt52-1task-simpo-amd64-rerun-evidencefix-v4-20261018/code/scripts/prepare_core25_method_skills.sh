#!/usr/bin/env bash
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXECUTOR_ROOT="$ROOT/skill-repair-benchmark"
TASK_FILE="$ROOT/configs/core25_tasks.txt"
RUN_ID="${1:-prepare-$(date -u +%Y%m%dT%H%M%SZ)}"
METHODS="${METHODS:-skillopt skillopt-lite}"
LOG_DIR="$ROOT/experiments/$RUN_ID/logs"
FAILURES=0

set -a
source "$ROOT/.env"
set +a

export UV_CACHE_DIR="${UV_CACHE_DIR:-/private/tmp/skillopt-eva-uv-cache}"
unset DEBUG
export PATH="/opt/homebrew/opt/python@3.12/libexec/bin:/opt/homebrew/bin:$PATH"
mkdir -p "$LOG_DIR"

cd "$EXECUTOR_ROOT"

run_logged() {
  local label="$1"
  local log_file="$2"
  shift 2
  echo "[$label] log=$log_file"
  if "$@" >"$log_file" 2>&1; then
    tail -20 "$log_file"
    return 0
  else
    local status=$?
    FAILURES=$((FAILURES + 1))
    echo "[$label] failed status=$status; showing last 80 log lines" >&2
    tail -80 "$log_file" >&2
    return "$status"
  fi
}

run_logged "check" "$LOG_DIR/00_check_environment.log" \
  /opt/homebrew/bin/uv run --locked python ../scripts/check_environment.py || exit 1
run_logged "metadata" "$LOG_DIR/01_metadata.log" \
  /opt/homebrew/bin/uv run --locked python ../scripts/init_run_metadata.py --run-id "$RUN_ID" || true

for method in $METHODS; do
  while IFS= read -r task_id; do
    [[ -z "$task_id" || "$task_id" == \#* ]] && continue
    run_logged "prepare:$method:$task_id" "$LOG_DIR/prepare_${method}_${task_id}.log" \
      /opt/homebrew/bin/uv run --locked python ../scripts/run_method.py --run-id "$RUN_ID" --method "$method" --task "$task_id" --prepare-only
  done < "$TASK_FILE"
done

echo "run_id=$RUN_ID failures=$FAILURES"
exit "$FAILURES"
