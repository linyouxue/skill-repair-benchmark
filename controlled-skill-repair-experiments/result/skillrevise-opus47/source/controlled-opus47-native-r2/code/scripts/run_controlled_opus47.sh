#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
stage="${1:-status}"
trial="${2:-single-flink-query-RI-001}"
case "$stage" in
  run|gold)
    set -a
    source .env.unified.local
    set +a
    export OPENAI_API_KEY="${TATU_API_KEY:-${OPENAI_API_KEY:-}}"
    test -n "$OPENAI_API_KEY" || { echo 'Missing Tatu API key' >&2; exit 2; }
    export OPENAI_BASE_URL="${OPENAI_BASE_URL:-https://maas.tatucloud.com/v1}"
    export BENCHFLOW_PROVIDER_BASE_URL="${OPENAI_BASE_URL%/v1}"
    export BENCHMARK_MODEL=tatu-anthropic/claude-opus-4-7
    export SKILL_REVISE_REVISION_LLM_PROVIDER=anthropic
    export SKILL_REVISE_REVISION_LLM_MODEL=claude-opus-4-7
    export SKILL_REVISE_REVISION_LLM_API_KEY="$OPENAI_API_KEY"
    export SKILL_REVISE_REVISION_LLM_BASE_URL="$OPENAI_BASE_URL"
    export SKILL_REVISE_REVISION_LLM_EFFORT=high
    export SKILL_REVISE_REVISION_LLM_THINKING=disabled
    export SKILL_REVISE_REVISION_LLM_MAX_TOKENS=32768
    export SKILL_REVISE_REVISION_LLM_HTTP_TIMEOUT=1200
    export SKILL_REVISE_REVISION_LLM_HTTP_RETRY_ATTEMPTS=1
    export SKILL_REVISE_LLM_COMMAND_ATTEMPTS=1
    export SKILL_REVISE_EVALUATION_RETRY_ATTEMPTS=1
    export SKILL_REVISE_BYPASS_PROXY=1
    unset BENCHMARK_REASONING_EFFORT
    ;;
esac
unset SKILL_REVISE_JPG_DIAGNOSIS_PACKAGE SKILL_REVISE_JPG_EVIDENCE_ROOT SKILL_REVISE_JPG_RESUME_REQUESTS
unset BENCHMARK_EXECUTOR_VERIFIER_HTTP_PROXY BENCHMARK_EXECUTOR_VERIFIER_HTTPS_PROXY BENCHMARK_EXECUTOR_VERIFIER_ALL_PROXY
export BENCHMARK_EXECUTOR_VERIFIER_PROXY_MODE=off
export BENCHFLOW_OPENHANDS_RUNTIME_VOLUME=benchflow-openhands-runtime-v2-glibc231
export BENCHFLOW_FORCE_SANDBOX_LITELLM=1
export BENCHFLOW_SANDBOX_LITELLM_VENV=/opt/benchflow/openhands-runtime/litellm-venv
export PYTHONUNBUFFERED=1
if [[ "$stage" == run || "$stage" == gold ]]; then
  bash scripts/bootstrap_unified_openhands_runtime_cache.sh
  bash scripts/patch_unified_egress_firewall_cap.sh
fi
.venv/bin/python scripts/controlled_opus47.py "$stage" --trial "$trial" \
  --work "${CONTROL_RUN_ROOT:-$PWD/runs/controlled-opus47-20261030}" \
  --package "${CONTROL_PACKAGE:-/home/eraser/skill-repair-controlled-datasets-20261020}"
