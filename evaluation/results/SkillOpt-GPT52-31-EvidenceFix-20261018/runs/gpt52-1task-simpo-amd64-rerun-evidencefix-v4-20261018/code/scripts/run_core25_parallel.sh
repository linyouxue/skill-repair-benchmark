#!/usr/bin/env bash
# Parallel Core-25 runner with N workers.
# Usage: scripts/run_core25_parallel.sh <run_id> [workers]
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXECUTOR_ROOT="$ROOT/skill-repair-benchmark"
TASK_FILE="$ROOT/configs/core25_tasks.txt"
RUN_ID="${1:-run-$(date -u +%Y%m%dT%H%M%SZ)}"
WORKERS="${2:-5}"
METHODS="${METHODS:-skillopt skillopt-lite}"
LOG_DIR="$ROOT/experiments/$RUN_ID/logs"
QUEUE_DIR="$ROOT/experiments/$RUN_ID/queue"
mkdir -p "$LOG_DIR" "$QUEUE_DIR"

set -a
# shellcheck disable=SC1091
source "$ROOT/.env"
set +a

export UV_CACHE_DIR="${UV_CACHE_DIR:-/private/tmp/skillopt-eva-uv-cache}"
unset DEBUG
export PATH="/opt/homebrew/opt/python@3.12/libexec/bin:/opt/homebrew/bin:$PATH"

cd "$EXECUTOR_ROOT"

run_logged() {
  local label="$1"
  local log_file="$2"
  shift 2
  echo "[$label] log=$log_file"
  if "$@" >"$log_file" 2>&1; then
    echo "[$label] ok"
    return 0
  else
    local status=$?
    echo "[$label] failed status=$status" >&2
    tail -40 "$log_file" >&2 || true
    return "$status"
  fi
}

build_queue() {
  local phase="$1"
  local queue_file="$QUEUE_DIR/${phase}.txt"
  local done_file="$QUEUE_DIR/${phase}.done"
  : >"$queue_file"
  : >"$done_file"
  while IFS= read -r task_id; do
    [[ -z "$task_id" || "$task_id" == \#* ]] && continue
    if [[ "$phase" == "baseline" ]]; then
      if [[ -f "$ROOT/experiments/$RUN_ID/baseline/original-skill/$task_id/benchmark_result.json" ]]; then
        echo "$task_id" >>"$done_file"
        continue
      fi
    else
      if [[ -f "$ROOT/experiments/$RUN_ID/methods/$phase/$task_id/method_result.json" ]]; then
        echo "$task_id" >>"$done_file"
        continue
      fi
    fi
    echo "$task_id" >>"$queue_file"
  done < "$TASK_FILE"
  echo "[queue] phase=$phase remaining=$(wc -l <"$queue_file" | tr -d ' ') skipped=$(wc -l <"$done_file" | tr -d ' ')"
}

worker_loop() {
  local worker_id="$1"
  local phase="$2"
  local queue_file="$QUEUE_DIR/${phase}.txt"
  local fail_file="$QUEUE_DIR/${phase}.failures"

  while true; do
    local task=""
    if ! task="$(python3 "$ROOT/scripts/claim_queue_task.py" "$queue_file")"; then
      break
    fi
    [[ -z "$task" ]] && break
    echo "[w${worker_id}][$phase] start $task"
    local log_file="$LOG_DIR/${phase}_${task}.w${worker_id}.log"
    local status=0
    if [[ "$phase" == "baseline" ]]; then
      /opt/homebrew/bin/uv run --locked python ../scripts/run_original_baseline.py \
        --run-id "$RUN_ID" --task "$task" >"$log_file" 2>&1 || status=$?
    else
      /opt/homebrew/bin/uv run --locked python ../scripts/run_method.py \
        --run-id "$RUN_ID" --method "$phase" --task "$task" >"$log_file" 2>&1 || status=$?
    fi
    if [[ "$status" -eq 0 ]]; then
      echo "[w${worker_id}][$phase] ok $task"
      echo "$task" >>"$QUEUE_DIR/${phase}.done"
    else
      echo "[w${worker_id}][$phase] FAIL $task status=$status" >&2
      echo "$task status=$status log=$log_file" >>"$fail_file"
      tail -30 "$log_file" >&2 || true
    fi
    # Refresh liveboard after each task finishes.
    python3 "$ROOT/scripts/export_liveboard.py" --run-id "$RUN_ID" >/dev/null 2>&1 || true
  done
  echo "[w${worker_id}][$phase] idle"
}

run_phase_parallel() {
  local phase="$1"
  build_queue "$phase"
  : >"$QUEUE_DIR/${phase}.failures"
  local pids=()
  local i
  for ((i=1; i<=WORKERS; i++)); do
    worker_loop "$i" "$phase" &
    pids+=("$!")
  done
  local pid
  for pid in "${pids[@]}"; do
    wait "$pid" || true
  done
  local fails=0
  if [[ -s "$QUEUE_DIR/${phase}.failures" ]]; then
    fails=$(wc -l <"$QUEUE_DIR/${phase}.failures" | tr -d ' ')
  fi
  echo "[phase] $phase complete failures=$fails"
  return 0
}

echo "run_id=$RUN_ID workers=$WORKERS"
run_logged "check" "$LOG_DIR/00_check_environment.log" \
  /opt/homebrew/bin/uv run --locked python ../scripts/check_environment.py || exit 1
run_logged "metadata" "$LOG_DIR/01_metadata.log" \
  /opt/homebrew/bin/uv run --locked python ../scripts/init_run_metadata.py --run-id "$RUN_ID" || true

# Warm docker bases used by Core-25 (best-effort, parallel, bounded wait).
echo "[docker] warming base images"
(
  docker pull ubuntu:24.04 &
  docker pull ubuntu:20.04 &
  docker pull python:3.12-slim &
  docker pull python:3.12.8-slim &
  docker pull jasonish/suricata:7.0.11 &
  wait
) >"$LOG_DIR/00_docker_pull.log" 2>&1 &
DOCKER_PULL_PID=$!
# Don't block the whole run forever on pulls.
( sleep 180; kill "$DOCKER_PULL_PID" >/dev/null 2>&1 || true ) &
wait "$DOCKER_PULL_PID" || true
echo "[docker] warm done (or timed out)"

run_phase_parallel "baseline"
for method in $METHODS; do
  run_phase_parallel "$method"
done

run_logged "summary" "$LOG_DIR/zz_summary.log" \
  /opt/homebrew/bin/uv run --locked python ../scripts/summarize_results.py --run-id "$RUN_ID"
python3 "$ROOT/scripts/export_liveboard.py" --run-id "$RUN_ID" || true

echo "DONE run_id=$RUN_ID"
if compgen -G "$QUEUE_DIR/*.failures" >/dev/null; then
  echo "failure files:"
  cat "$QUEUE_DIR"/*.failures || true
fi
