#!/usr/bin/env bash
# Source this file; it intentionally prints no credentials.

set -a
source "/Users/elsie/Desktop/SkillOpt-eva/.env"
set +a

if [[ -z "${TATU_API_KEY:-}" || -z "${TATU_BASE_URL:-}" ]]; then
  echo "TATU_API_KEY or TATU_BASE_URL is missing from .env" >&2
  return 1 2>/dev/null || exit 1
fi

export MODEL_PROVIDER="tatu"
export TATU_MODEL="claude-opus-4-7"
export SKILLOPT_MODEL="claude-opus-4-7"
export SKILLOPT_API_BASE="$TATU_BASE_URL"
export BENCHMARK_MODEL="tatu/claude-opus-4-7"
export BENCHMARK_REASONING_EFFORT=""

export OPENAI_API_KEY="$TATU_API_KEY"
export OPENAI_API_BASE="$TATU_BASE_URL"
export OPENAI_BASE_URL="$TATU_BASE_URL"

export SKILLOPT_EVA_DIAGNOSIS_N="3"
export SKILLOPT_EVA_EDIT_BUDGET_L="4"
export SKILLOPT_EVA_REPAIR_ROUNDS_R="2"
export SKILLOPT_EVA_DIAGNOSIS_PARALLEL="0"
export SKILLOPT_EVA_SMOKE="0"
export UV_CACHE_DIR="/Users/elsie/Desktop/SkillOpt-eva/.uv-cache"
