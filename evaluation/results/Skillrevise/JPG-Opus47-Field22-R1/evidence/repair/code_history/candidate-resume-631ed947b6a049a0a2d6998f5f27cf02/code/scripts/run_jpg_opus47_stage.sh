#!/usr/bin/env bash
# Pure Opus experiment: distinct result paths; no GPT responses or diagnoses.
set -euo pipefail
cd "$(dirname "$0")/.."
stage="${1:-status}"
if [[ "$stage" == probe || "$stage" == repair || "$stage" == final || "$stage" == recover_export ]]; then
  set -a
  source .env.unified.local
  set +a
  export OPENAI_API_KEY="${TATU_API_KEY:-${OPENAI_API_KEY:-}}"
  [[ -n "$OPENAI_API_KEY" ]] || { echo 'Missing Tatu API key in .env.unified.local' >&2; exit 2; }
  export OPENAI_BASE_URL="${OPENAI_BASE_URL:-${BENCHFLOW_PROVIDER_BASE_URL:-https://maas.tatucloud.com/v1}}"
  export OPENAI_BASE_URL="${OPENAI_BASE_URL%/}"
  [[ "$OPENAI_BASE_URL" == */v1 ]] || export OPENAI_BASE_URL="$OPENAI_BASE_URL/v1"
  # Direct calls append /messages; LiteLLM itself appends /v1/messages.
  export BENCHFLOW_PROVIDER_BASE_URL="${OPENAI_BASE_URL%/v1}"
  export BENCHMARK_MODEL=tatu-anthropic/claude-opus-4-7
  unset BENCHMARK_REASONING_EFFORT
  export SKILL_REVISE_REVISION_LLM_PROVIDER=anthropic
  export SKILL_REVISE_REVISION_LLM_MODEL=claude-opus-4-7
  export SKILL_REVISE_REVISION_LLM_API_KEY="$OPENAI_API_KEY"
  export SKILL_REVISE_REVISION_LLM_BASE_URL="$OPENAI_BASE_URL"
  export SKILL_REVISE_REVISION_LLM_MAX_TOKENS=32768
  export SKILL_REVISE_REVISION_LLM_TEMPERATURE=1.0
  export SKILL_REVISE_REVISION_LLM_EFFORT=high
  export SKILL_REVISE_REVISION_LLM_THINKING=disabled
  unset SKILL_REVISE_REVISION_LLM_SYSTEM_PROMPT SKILL_REVISE_REVISION_LLM_SEED
  unset SKILL_HARNESS_REVISION_LLM_SYSTEM_PROMPT SKILL_HARNESS_REVISION_LLM_SEED
  export SKILL_REVISE_BYPASS_PROXY=1
  export SKILL_REVISE_REVISION_LLM_HTTP_TIMEOUT=1200
  export SKILL_REVISE_REVISION_LLM_HTTP_RETRY_ATTEMPTS=1
  export SKILL_REVISE_LLM_COMMAND_ATTEMPTS=1
  export SKILL_REVISE_EVALUATION_RETRY_ATTEMPTS=1
  export SKILL_REVISE_JPG_RESUME_REQUESTS=1
fi
# Verifier uses baked offline dependencies; do not inherit an unreachable proxy.
unset BENCHMARK_EXECUTOR_VERIFIER_HTTP_PROXY BENCHMARK_EXECUTOR_VERIFIER_HTTPS_PROXY BENCHMARK_EXECUTOR_VERIFIER_ALL_PROXY
export BENCHMARK_EXECUTOR_VERIFIER_PROXY_MODE=off
export SKILL_REVISE_JPG_DIAGNOSIS_PACKAGE=/mnt/d/project/skillrevise-handoff-experiments/data/jpg-field-accuracy-diagnosis-20261022
export SKILL_REVISE_JPG_EVIDENCE_ROOT="$PWD/runs/jpg-opus47-field22-r1/evidence/repair_requests"
export BENCHFLOW_OPENHANDS_RUNTIME_VOLUME=benchflow-openhands-runtime-v2-glibc231
export BENCHFLOW_FORCE_SANDBOX_LITELLM=1
export BENCHFLOW_SANDBOX_LITELLM_VENV=/opt/benchflow/openhands-runtime/litellm-venv
export PYTHONUNBUFFERED=1
.venv/bin/python scripts/jpg_opus47_workflow.py "$stage"
