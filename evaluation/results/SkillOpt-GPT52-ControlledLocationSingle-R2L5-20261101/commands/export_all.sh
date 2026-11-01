#!/usr/bin/env bash
set -euo pipefail
ROOT="/Users/elsie/Desktop/SkillOpt-eva"
RUN="$ROOT/experiments/gpt52-skillopt-controlled-location-single-r2l5-v2-20261027"
RUNNER="$ROOT/skill-repair-controlled-datasets-20261020/tools/runner.py"
while IFS= read -r trial || [[ -n "$trial" ]]; do
  [[ -z "$trial" || "$trial" == \#* ]] && continue
  dataset="${trial%%-*}"
  python3 -B "$RUNNER" export --trial "$trial" --out "$RUN/inputs/$dataset/$trial" --language zh
done < "$RUN/configs/trials.txt"

