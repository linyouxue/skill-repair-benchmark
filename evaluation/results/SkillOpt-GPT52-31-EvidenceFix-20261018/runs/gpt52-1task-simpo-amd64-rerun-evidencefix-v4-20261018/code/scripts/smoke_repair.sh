#!/usr/bin/env bash
# Cheap smoke: n=1, R=1 via SKILLOPT_EVA_SMOKE=1.
# Usage:
#   ./scripts/smoke_repair.sh <task_id> [method] [run_id]
# Examples:
#   ./scripts/smoke_repair.sh suricata-rule-tuning
#   ./scripts/smoke_repair.sh suricata-rule-tuning skillopt-lite smoke-$(date -u +%Y%m%dT%H%M%SZ)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TASK="${1:?task_id required}"
METHOD="${2:-skillopt}"
RUN_ID="${3:-smoke-$(date -u +%Y%m%dT%H%M%SZ)}"
export SKILLOPT_EVA_SMOKE=1
# Prefer project .env if present (does not overwrite already-exported vars).
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi
export SKILLOPT_EVA_SMOKE=1
cd "$ROOT"
echo "[smoke] SKILLOPT_EVA_SMOKE=1 method=$METHOD task=$TASK run_id=$RUN_ID"
exec python3 scripts/run_method.py --method "$METHOD" --task "$TASK" --run-id "$RUN_ID" --prepare-only
