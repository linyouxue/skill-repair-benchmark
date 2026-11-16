#!/usr/bin/env bash
# No embedded Python/heredocs/keys in the PowerShell commands used by the user.
set -euo pipefail
cd "$(dirname "$0")/.."
stage="${1:-status}"
if [[ "$stage" == prepare ]] && ! .venv/bin/python -c 'import openpyxl; assert openpyxl.__version__ == "3.1.5"' >/dev/null 2>&1; then
  if command -v uv >/dev/null 2>&1; then
    uv pip install --python .venv/bin/python openpyxl==3.1.5
  else
    .venv/bin/python -m pip install openpyxl==3.1.5
  fi
fi
if [[ "$stage" == probe || "$stage" == repair || "$stage" == final ]]; then
  set -a
  source .env.unified.local
  set +a
  export OPENAI_API_KEY="${TATU_API_KEY:-${OPENAI_API_KEY:-}}"
  export OPENAI_BASE_URL="${OPENAI_BASE_URL:-${BENCHFLOW_PROVIDER_BASE_URL:-https://maas.tatucloud.com/v1}}"
  [[ -n "$OPENAI_API_KEY" ]] || { echo 'Missing existing Tatu API key in .env.unified.local' >&2; exit 2; }
  export SKILL_REVISE_REVISION_LLM_PROVIDER=openai
  export SKILL_REVISE_REVISION_LLM_MODEL=gpt-5.5
  export SKILL_REVISE_REVISION_LLM_API_KEY="$OPENAI_API_KEY"
  export SKILL_REVISE_REVISION_LLM_BASE_URL="$OPENAI_BASE_URL"
  export SKILL_REVISE_REVISION_LLM_MAX_TOKENS="${JPG_GPT55_MAX_TOKENS:-8192}"
  export SKILL_REVISE_REVISION_LLM_EFFORT=''
  # Empty canonical values override local Claude defaults; clear legacy aliases.
  export SKILL_REVISE_REVISION_LLM_THINKING=''
  unset SKILL_HARNESS_REVISION_LLM_THINKING SKILL_HARNESS_REVISION_LLM_EFFORT
  export SKILL_REVISE_BYPASS_PROXY=1
  export SKILL_REVISE_REVISION_LLM_HTTP_TIMEOUT=1200
  export SKILL_REVISE_REVISION_LLM_HTTP_RETRY_ATTEMPTS=1
  export SKILL_REVISE_LLM_COMMAND_ATTEMPTS=1
  export SKILL_REVISE_EVALUATION_RETRY_ATTEMPTS=1
  export SKILL_REVISE_JPG_RESUME_REQUESTS=1
fi
export SKILL_REVISE_JPG_DIAGNOSIS_PACKAGE=/mnt/d/project/skillrevise-handoff-experiments/data/jpg-field-accuracy-diagnosis-20261022
export SKILL_REVISE_JPG_EVIDENCE_ROOT="$PWD/runs/jpg-gpt55-field22-r1/evidence/repair_requests"
export BENCHFLOW_OPENHANDS_RUNTIME_VOLUME=benchflow-openhands-runtime-v2-glibc231
export BENCHFLOW_FORCE_SANDBOX_LITELLM=1
export BENCHFLOW_SANDBOX_LITELLM_VENV=/opt/benchflow/openhands-runtime/litellm-venv
export PYTHONUNBUFFERED=1
.venv/bin/python scripts/jpg_gpt55_workflow.py "$stage"
