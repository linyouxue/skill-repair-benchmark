#!/usr/bin/env bash
set -a
source "/Users/elsie/Desktop/SkillOpt-eva/.env"
set +a

_controlled_legacy_value() {
  local key="$1"
  local value
  value="$(sed -nE "s/^[[:space:]]*#[[:space:]]*${key}[[:space:]]*=[[:space:]]*(.*)$/\\1/p" "/Users/elsie/Desktop/SkillOpt-eva/.env" | tail -n 1)"
  value="${value%\"}"; value="${value#\"}"
  value="${value%\'}"; value="${value#\'}"
  printf '%s' "$value"
}

export AI360_API_KEY="${AI360_API_KEY:-$(_controlled_legacy_value AI360_API_KEY)}"
export AI360_BASE_URL="${AI360_BASE_URL:-$(_controlled_legacy_value AI360_BASE_URL)}"
if [[ -z "$AI360_API_KEY" || -z "$AI360_BASE_URL" ]]; then
  echo "GPT-5.2 AI360 credentials are missing" >&2
  return 1 2>/dev/null || exit 1
fi

export TATU_API_KEY=""
export TATU_BASE_URL=""
export TATU_MODEL=""
export AWS_BEARER_TOKEN_BEDROCK=""
export MODEL_PROVIDER="ai360"
export AI360_MODEL="openai/gpt-5.2"
export SKILLOPT_MODEL="openai/gpt-5.2"
export SKILLOPT_API_BASE="$AI360_BASE_URL"
export BENCHMARK_MODEL="ai360/openai/gpt-5.2"
# The AI360 GPT-5.2 endpoint rejects OpenHands' implicit "high" default and
# advertises "medium" as the supported value. Pin it for comparable eval runs.
export BENCHMARK_REASONING_EFFORT="medium"
export OPENAI_API_KEY="$AI360_API_KEY"
export OPENAI_API_BASE="$AI360_BASE_URL"
export OPENAI_BASE_URL="$AI360_BASE_URL"
export LLM_API_KEY="$AI360_API_KEY"
export LLM_API_BASE="$AI360_BASE_URL"

export SKILLOPT_EVA_DIAGNOSIS_N="3"
export SKILLOPT_EVA_EDIT_BUDGET_L="5"
export SKILLOPT_EVA_REPAIR_ROUNDS_R="2"
export SKILLOPT_EVA_DIAGNOSIS_PARALLEL="0"
export SKILLOPT_EVA_SHARED_DIAGNOSIS="0"
unset SKILLOPT_EVA_DIAGNOSIS_SOURCE_RUN
export SKILLOPT_EVA_USE_UPSTREAM_REWRITE="0"
export SKILLOPT_EVA_UPDATE_MODE="patch"
export SKILLOPT_EVA_EDIT_FORMAT_ATTEMPTS="3"
export OPENAI_COMPATIBLE_TEMPERATURE=""
export OPTIMIZER_OPENAI_COMPATIBLE_TEMPERATURE=""
export TARGET_OPENAI_COMPATIBLE_TEMPERATURE=""
export PYTHONPATH="/Users/elsie/Desktop/SkillOpt-eva/skill-repair-benchmark/src:/Users/elsie/Desktop/SkillOpt-eva"
export UV_CACHE_DIR="/Users/elsie/Desktop/SkillOpt-eva/.uv-cache"
# LiteLLM parses DEBUG as a boolean. The repository-level .env carries
# DEBUG=release for an unrelated workflow, which makes its proxy exit before
# the first model request.
export DEBUG="0"
export CONTROLLED_EXPERIMENT_ID="gpt52-skillopt-controlled-location-single-r2l5-v2-20261027"
export CONTROLLED_TRACE_ROOT="/Users/elsie/Desktop/SkillOpt-eva/experiments/gpt52-skillopt-controlled-location-single-r2l5-v2-20261027/repair_traces"

case "$MODEL_PROVIDER/$SKILLOPT_MODEL/$BENCHMARK_MODEL" in
  *opus*|*claude*|*tatu*) echo "Refusing non-GPT controlled environment" >&2; return 1 2>/dev/null || exit 1 ;;
esac
[[ "$MODEL_PROVIDER" == "ai360" ]]
[[ "$SKILLOPT_MODEL" == "openai/gpt-5.2" ]]
[[ "$BENCHMARK_MODEL" == "ai360/openai/gpt-5.2" ]]
unset -f _controlled_legacy_value

