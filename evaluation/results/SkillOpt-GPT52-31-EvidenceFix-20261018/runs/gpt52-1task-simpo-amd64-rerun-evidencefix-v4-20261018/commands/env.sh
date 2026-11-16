#!/usr/bin/env bash
# Source this file; it intentionally prints no credentials.

set -a
source "/Users/elsie/Desktop/SkillOpt-eva/.env"
set +a

_legacy_ai360_value() {
  local key="$1"
  local value
  value="$(sed -nE "s/^[[:space:]]*#[[:space:]]*${key}[[:space:]]*=[[:space:]]*(.*)$/\\1/p" "/Users/elsie/Desktop/SkillOpt-eva/.env" | tail -n 1)"
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"
  printf '%s' "$value"
}

export AI360_API_KEY="${AI360_API_KEY:-$(_legacy_ai360_value AI360_API_KEY)}"
export AI360_BASE_URL="${AI360_BASE_URL:-$(_legacy_ai360_value AI360_BASE_URL)}"
if [[ -z "$AI360_API_KEY" || -z "$AI360_BASE_URL" ]]; then
  echo "AI360_API_KEY or AI360_BASE_URL is missing from .env" >&2
  return 1 2>/dev/null || exit 1
fi

export MODEL_PROVIDER="ai360"
export AI360_MODEL="openai/gpt-5.2"
export SKILLOPT_MODEL="openai/gpt-5.2"
export SKILLOPT_API_BASE="$AI360_BASE_URL"
export BENCHMARK_MODEL="ai360/openai/gpt-5.2"
# OpenHands does not expose an ACP reasoning-effort option. Leave this unset;
# the exact model remains openai/gpt-5.2 for both optimization and the gate.
export BENCHMARK_REASONING_EFFORT=""

# Omit temperature so the 360 OpenAI-compatible route can apply the model's
# supported default without receiving an incompatible request parameter.
export OPENAI_COMPATIBLE_TEMPERATURE=""
export OPTIMIZER_OPENAI_COMPATIBLE_TEMPERATURE=""
export TARGET_OPENAI_COMPATIBLE_TEMPERATURE=""

export OPENAI_API_KEY="$AI360_API_KEY"
export OPENAI_API_BASE="$AI360_BASE_URL"
export OPENAI_BASE_URL="$AI360_BASE_URL"
export LLM_API_KEY="$AI360_API_KEY"
export LLM_API_BASE="$AI360_BASE_URL"

export SKILLOPT_EVA_DIAGNOSIS_N="3"
export SKILLOPT_EVA_EDIT_BUDGET_L="4"
export SKILLOPT_EVA_REPAIR_ROUNDS_R="2"
export SKILLOPT_EVA_DIAGNOSIS_PARALLEL="0"
export SKILLOPT_EVA_SMOKE="0"
export SKILLOPT_EVA_EDIT_FORMAT_ATTEMPTS="3"
export SKILLOPT_EVA_SHARED_DIAGNOSIS="0"
export SKILLOPT_EVA_USE_UPSTREAM_REWRITE="0"
export SKILLOPT_EVA_GATE_INFRA_ATTEMPTS="2"
export SKILLOPT_EVA_AGENT_INSTALL_TIMEOUT="3600"
export UV_CACHE_DIR="/Users/elsie/Desktop/SkillOpt-eva/.uv-cache"

unset -f _legacy_ai360_value
