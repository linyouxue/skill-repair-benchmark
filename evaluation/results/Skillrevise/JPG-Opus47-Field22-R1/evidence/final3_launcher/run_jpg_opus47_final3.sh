#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "${1:-}" != --status ]]; then
  set -a
  source .env.unified.local
  set +a
  export OPENAI_API_KEY="${TATU_API_KEY:-${OPENAI_API_KEY:-}}"
  [[ -n "$OPENAI_API_KEY" ]] || { echo 'Missing Tatu key'; exit 2; }
  export OPENAI_BASE_URL="${OPENAI_BASE_URL:-${BENCHFLOW_PROVIDER_BASE_URL:-https://maas.tatucloud.com/v1}}"
  export OPENAI_BASE_URL="${OPENAI_BASE_URL%/}"
  [[ "$OPENAI_BASE_URL" == */v1 ]] || export OPENAI_BASE_URL="$OPENAI_BASE_URL/v1"
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
fi
unset BENCHMARK_EXECUTOR_VERIFIER_HTTP_PROXY BENCHMARK_EXECUTOR_VERIFIER_HTTPS_PROXY BENCHMARK_EXECUTOR_VERIFIER_ALL_PROXY
export BENCHMARK_EXECUTOR_VERIFIER_PROXY_MODE=off
export BENCHFLOW_OPENHANDS_RUNTIME_VOLUME=benchflow-openhands-runtime-v2-glibc231
export BENCHFLOW_FORCE_SANDBOX_LITELLM=1
export BENCHFLOW_SANDBOX_LITELLM_VENV=/opt/benchflow/openhands-runtime/litellm-venv
export PYTHONUNBUFFERED=1
.venv/bin/python scripts/jpg_opus47_final3.py "$@"
