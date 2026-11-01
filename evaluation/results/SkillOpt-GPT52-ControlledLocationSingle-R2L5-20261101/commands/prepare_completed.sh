#!/usr/bin/env bash
set -euo pipefail
ROOT="/Users/elsie/Desktop/SkillOpt-eva"
RUN="$ROOT/experiments/gpt52-skillopt-controlled-location-single-r2l5-v2-20261027"
RUNNER="$ROOT/skill-repair-controlled-datasets-20261020/tools/runner.py"
while IFS= read -r trial || [[ -n "$trial" ]]; do
  [[ -z "$trial" || "$trial" == \#* ]] && continue
  dataset="${trial%%-*}"
  candidate_hash="$(find "$RUN/candidates/$dataset/$trial" -maxdepth 2 -name CANDIDATE_SHA256.json -print -quit 2>/dev/null || true)"
  [[ -z "$candidate_hash" ]] && continue
  candidate="$(dirname "$candidate_hash")"
  attempt="$(basename "$candidate")"
  prepared="$RUN/prepared/repaired/$dataset/$trial/$attempt"
  if [[ -f "$prepared/PREPARED_SHA256.json" ]]; then
    continue
  fi
  python3 -B "$RUNNER" prepare-eval --trial "$trial" --candidate "$candidate" --out "$prepared"
done < "$RUN/configs/trials.txt"

