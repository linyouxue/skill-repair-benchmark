#!/usr/bin/env bash
set -u -o pipefail
ROOT="/Users/elsie/Desktop/SkillOpt-eva"
RUN="$ROOT/experiments/gpt52-skillopt-controlled-location-single-r2l5-v2-20261027"
RUNNER="$ROOT/skill-repair-controlled-datasets-20261020/tools/runner.py"
BENCH="$ROOT/skill-repair-benchmark/.venv/bin/bench"
worker="${1:?worker index required}"
workers="${2:?worker count required}"
source "$RUN/commands/env.sh"
mkdir -p "$RUN/terminal_logs"
log="$RUN/terminal_logs/eval-worker-$worker.log"
index=0
failures=0
while IFS= read -r trial || [[ -n "$trial" ]]; do
  [[ -z "$trial" || "$trial" == \#* ]] && continue
  case "$trial" in
    *dialogue-parser*|*flink-query*|*pddl-airport-planning*|*video-silence-remover*) assigned=0 ;;
    *) assigned=1 ;;
  esac
  if (( assigned % workers == worker )); then
    dataset="${trial%%-*}"
    prepared_hash="$(find "$RUN/prepared/repaired/$dataset/$trial" -maxdepth 2 -name PREPARED_SHA256.json -print -quit 2>/dev/null || true)"
    if [[ -z "$prepared_hash" ]]; then
      printf '[%s] skip-no-candidate %s\n' "$(date -u +%FT%TZ)" "$trial" | tee -a "$log"
      index=$((index + 1)); continue
    fi
    prepared="$(dirname "$prepared_hash")"
    attempt="$(basename "$prepared")"
    eval_root="$RUN/eval_runs/repaired/$dataset/$trial/$attempt"
    complete="$(find "$eval_root" -maxdepth 2 -name RUN_RECORD.json -exec grep -l '\"bench_exit_code\": 0' {} \; -quit 2>/dev/null || true)"
    if [[ -n "$complete" ]]; then
      printf '[%s] skip-complete %s\n' "$(date -u +%FT%TZ)" "$trial" | tee -a "$log"
      index=$((index + 1)); continue
    fi
    rep=1
    while [[ -e "$eval_root/rep-$(printf '%03d' "$rep")" ]]; do
      rep=$((rep + 1))
    done
    jobs="$eval_root/rep-$(printf '%03d' "$rep")"
    if [[ "$trial" == *flink-query* || "$trial" == *fix-build-google-auto* ]]; then
      export DOCKER_DEFAULT_PLATFORM="linux/amd64"
    else
      unset DOCKER_DEFAULT_PLATFORM
    fi
    printf '[%s] start %s\n' "$(date -u +%FT%TZ)" "$trial" | tee -a "$log"
    reasoning_args=()
    if [[ -n "${BENCHMARK_REASONING_EFFORT:-}" ]]; then
      reasoning_args=(--reasoning-effort "$BENCHMARK_REASONING_EFFORT")
    fi
    if python3 -B "$RUNNER" eval --prepared "$prepared" --jobs "$jobs" \
      --agent openhands --model ai360/openai/gpt-5.2 --sandbox docker --bench "$BENCH" \
      "${reasoning_args[@]}" \
      --method skillopt-controlled-oracle-hint-r2l5-v2 --repair-model openai/gpt-5.2 \
      2>&1 | tee -a "$log"; then
      printf '[%s] complete %s\n' "$(date -u +%FT%TZ)" "$trial" | tee -a "$log"
    else
      failures=$((failures + 1))
      printf '[%s] failed %s\n' "$(date -u +%FT%TZ)" "$trial" | tee -a "$log"
    fi
  fi
  index=$((index + 1))
done < "$RUN/configs/trials.txt"
exit "$failures"

