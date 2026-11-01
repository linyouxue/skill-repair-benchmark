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
log="$RUN/terminal_logs/control-eval-worker-$worker.log"
index=0
failures=0
while IFS=$'\t' read -r condition item || [[ -n "$condition" ]]; do
  [[ -z "$condition" || "$condition" == \#* ]] && continue
  case "$item" in
    *dialogue-parser*|*flink-query*|*pddl-airport-planning*|*video-silence-remover*) assigned=0 ;;
    *) assigned=1 ;;
  esac
  if (( assigned % workers == worker )); then
    prepared="$RUN/prepared/controls/$condition/$item"
    eval_root="$RUN/eval_runs/controls/$condition/$item"
    complete="$(find "$eval_root" -maxdepth 2 -name RUN_RECORD.json -exec grep -l '\"bench_exit_code\": 0' {} \; -quit 2>/dev/null || true)"
    if [[ -n "$complete" ]]; then
      printf '[%s] skip-complete %s/%s\n' "$(date -u +%FT%TZ)" "$condition" "$item" | tee -a "$log"
      index=$((index + 1)); continue
    fi
    rep=1
    while [[ -e "$eval_root/rep-$(printf '%03d' "$rep")" ]]; do
      rep=$((rep + 1))
    done
    jobs="$eval_root/rep-$(printf '%03d' "$rep")"
    if [[ "$item" == *flink-query* || "$item" == *fix-build-google-auto* ]]; then
      export DOCKER_DEFAULT_PLATFORM="linux/amd64"
    else
      unset DOCKER_DEFAULT_PLATFORM
    fi
    printf '[%s] start %s/%s\n' "$(date -u +%FT%TZ)" "$condition" "$item" | tee -a "$log"
    reasoning_args=()
    if [[ -n "${BENCHMARK_REASONING_EFFORT:-}" ]]; then
      reasoning_args=(--reasoning-effort "$BENCHMARK_REASONING_EFFORT")
    fi
    if python3 -B "$RUNNER" eval --prepared "$prepared" --jobs "$jobs" \
      --agent openhands --model ai360/openai/gpt-5.2 --sandbox docker --bench "$BENCH" \
      "${reasoning_args[@]}" \
      --method control --repair-model none 2>&1 | tee -a "$log"; then
      printf '[%s] complete %s/%s\n' "$(date -u +%FT%TZ)" "$condition" "$item" | tee -a "$log"
    else
      failures=$((failures + 1))
      printf '[%s] failed %s/%s\n' "$(date -u +%FT%TZ)" "$condition" "$item" | tee -a "$log"
    fi
  fi
  index=$((index + 1))
done < "$RUN/configs/controls.tsv"
exit "$failures"

