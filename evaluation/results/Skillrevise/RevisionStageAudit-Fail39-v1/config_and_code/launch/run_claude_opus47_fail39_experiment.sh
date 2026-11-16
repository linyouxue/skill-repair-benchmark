#!/usr/bin/env bash
# Run a fresh No-Skill and bundle-aware SkillRevise comparison on the 39
# published Original-Skill failures, using Tatu's Claude Opus 4.7 model.
#
# This does not reuse the GPT-5.2 No-Skill result: the baseline must be run
# with the same rollout model as SkillRevise for a valid comparison.

set -euo pipefail

METHOD_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_LABEL="${SKILL_REVISE_CLAUDE_OPUS47_RUN_LABEL:-tatu-claude-opus47-fail39-published-trace-r3}"
METHOD_ID="${SKILL_REVISE_CLAUDE_OPUS47_METHOD_ID:-skillrevise-bundle-claude-opus47-fail39-published-trace-top3-r3}"
TASKS_ROOT="${SKILL_REVISE_UNIFIED_TASKS_ROOT:-$HOME/skillsbench-unified-overlay-gpt52fail39/tasks}"
SOURCE_MANIFEST="${SKILL_REVISE_CLAUDE_OPUS47_SOURCE_MANIFEST:-$METHOD_ROOT/manifests/gpt52-representative-fail39-latest_tasks.json}"
MANIFEST="${SKILL_REVISE_CLAUDE_OPUS47_MANIFEST:-$METHOD_ROOT/manifests/claude-opus47-representative-fail39-civ6-last_tasks.json}"
PREBUILT_IMAGES="${SKILL_REVISE_CLAUDE_OPUS47_PREBUILT_IMAGES:-$METHOD_ROOT/runs/unified/tatu-claude-opus47-fail39-prebuilt/prebuilt_images.json}"
PREBUILT_IMAGE_SEED="$METHOD_ROOT/runs/unified/gpt52-representative-fail39-latest/prebuilt_images.json"
RESULTS_ROOT="$METHOD_ROOT/runs/unified/$RUN_LABEL"
JOBS_ROOT="$HOME/benchmark-jobs/$RUN_LABEL"
CANDIDATES_ROOT="$HOME/benchmark-candidates/$RUN_LABEL"
PUBLISHED_ORIGINAL_TRACES="${SKILL_REVISE_CLAUDE_OPUS47_PUBLISHED_ORIGINAL_TRACES:-$METHOD_ROOT/runs/framework-backups/20260920/evaluation-results/GPT52-AllTasks-RepresentativeRuns-20260916}"

cd "$METHOD_ROOT"
# shellcheck disable=SC1091
source .env.unified.local

if [[ -z "${TATU_API_KEY:-}" || "$TATU_API_KEY" == '<PASTE_TATU_CLOUD_API_KEY_HERE>' ]]; then
  echo "Set TATU_API_KEY in $METHOD_ROOT/.env.unified.local first." >&2
  exit 2
fi
for required_path in "$TASKS_ROOT" "$SOURCE_MANIFEST" "$PREBUILT_IMAGE_SEED" "$PUBLISHED_ORIGINAL_TRACES"; do
  [[ -e "$required_path" ]] || { echo "Missing required path: $required_path" >&2; exit 2; }
done
docker info >/dev/null 2>&1 || {
  DOCKER_READY=0
}
DOCKER_READY="${DOCKER_READY:-1}"

# Tatu lists Claude on /models but serves it only through its native Anthropic
# Messages protocol, not OpenAI /chat/completions. The SkillRevise adapter
# registers this explicit provider route in-process before the executor starts.
export BENCHMARK_MODEL="${SKILL_REVISE_CLAUDE_OPUS47_MODEL:-tatu-anthropic/claude-opus-4-7}"
# OpenHands 1.28.1 does not advertise an ACP ``reasoning_effort`` session
# option. Passing it through --unified-reasoning-effort therefore rejects the
# session before its first prompt. Opus 4.7's native default is high; omit the
# unsupported ACP option for rollouts and retain explicit high for the direct
# SkillRevise author/diagnosis/revision API calls below.
export SKILL_REVISE_CLAUDE_OPUS47_EFFORT="${SKILL_REVISE_CLAUDE_OPUS47_EFFORT:-high}"
unset BENCHMARK_REASONING_EFFORT

# These parameters apply to the direct LLM calls that perform bundle skill
# selection, diagnosis, and revision. The preflight below verifies that Tatu
# accepts them before Docker rollouts begin.
export OPENAI_BASE_URL="${OPENAI_BASE_URL:-${BENCHFLOW_PROVIDER_BASE_URL:-https://maas.tatucloud.com/v1}}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-${TATU_API_KEY}}"
# The direct Anthropic client calls "$OPENAI_BASE_URL/messages" and therefore
# needs the /v1 suffix. LiteLLM's Anthropic provider appends /v1/messages
# itself, so it must receive the endpoint root instead of /v1; otherwise its
# upstream request becomes /v1/v1/messages and Tatu rejects it.
export BENCHFLOW_PROVIDER_BASE_URL="${SKILL_REVISE_CLAUDE_OPUS47_LITELLM_BASE_URL:-${OPENAI_BASE_URL%/v1}}"
export SKILL_REVISE_REVISION_LLM_PROVIDER=anthropic
export SKILL_REVISE_REVISION_LLM_MODEL="${SKILL_REVISE_CLAUDE_OPUS47_REVISION_MODEL:-claude-opus-4-7}"
export SKILL_REVISE_REVISION_LLM_BASE_URL="$OPENAI_BASE_URL"
export SKILL_REVISE_REVISION_LLM_API_KEY="$OPENAI_API_KEY"
export SKILL_REVISE_REVISION_LLM_TEMPERATURE="${SKILL_REVISE_CLAUDE_OPUS47_TEMPERATURE:-1.0}"
export SKILL_REVISE_REVISION_LLM_EFFORT="$SKILL_REVISE_CLAUDE_OPUS47_EFFORT"
export SKILL_REVISE_REVISION_LLM_THINKING=disabled
export SKILL_REVISE_REVISION_LLM_MAX_TOKENS="${SKILL_REVISE_CLAUDE_OPUS47_MAX_TOKENS:-32768}"
export SKILL_REVISE_BYPASS_PROXY=1
export SKILL_REVISE_REVISION_LLM_HTTP_RETRY_ATTEMPTS="${SKILL_REVISE_CLAUDE_OPUS47_LLM_RETRY_ATTEMPTS:-6}"
export SKILL_REVISE_REVISION_LLM_HTTP_RETRY_BASE_DELAY_SECONDS="${SKILL_REVISE_CLAUDE_OPUS47_LLM_RETRY_DELAY_SECONDS:-3}"
# Retry the whole command as well: a transient WSL route outage can occur
# before the command client's own HTTP retry loop receives a response.
export SKILL_REVISE_LLM_COMMAND_ATTEMPTS="${SKILL_REVISE_CLAUDE_OPUS47_COMMAND_ATTEMPTS:-3}"
export SKILL_REVISE_LLM_COMMAND_RETRY_DELAY_SECONDS="${SKILL_REVISE_CLAUDE_OPUS47_COMMAND_RETRY_DELAY_SECONDS:-10}"
export SKILL_REVISE_FAIL39_PRINCIPLE_RETRIEVAL="${SKILL_REVISE_CLAUDE_OPUS47_PRINCIPLE_RETRIEVAL:-bm25}"

# Verifiers run without a proxy by default.  This workstation's task
# containers have direct HTTPS egress, whereas a proxy bound only to Windows
# loopback is not reachable through host.docker.internal and would turn every
# rollout into an infrastructure error during its preflight.  A known
# Docker-reachable relay can still be opted into explicitly.
VERIFIER_PROXY="${SKILL_REVISE_CLAUDE_OPUS47_VERIFIER_PROXY:-}"
unset BENCHMARK_EXECUTOR_VERIFIER_HTTP_PROXY BENCHMARK_EXECUTOR_VERIFIER_HTTPS_PROXY \
  BENCHMARK_EXECUTOR_VERIFIER_ALL_PROXY
if [[ -n "$VERIFIER_PROXY" ]]; then
  export BENCHMARK_EXECUTOR_VERIFIER_HTTPS_PROXY="$VERIFIER_PROXY"
  export BENCHMARK_EXECUTOR_VERIFIER_PROXY_MODE=explicit
  VERIFIER_PROXY_MODE=explicit
else
  export BENCHMARK_EXECUTOR_VERIFIER_PROXY_MODE=off
  VERIFIER_PROXY_MODE=off
fi

# Reuse local task images and the pinned OpenHands runtime. Images are task
# environments, so they are independent of the model selection.
export BENCHFLOW_OPENHANDS_RUNTIME_VOLUME=benchflow-openhands-runtime-v2-glibc231
export BENCHFLOW_FORCE_SANDBOX_LITELLM=1
export BENCHFLOW_SANDBOX_LITELLM_VENV=/opt/benchflow/openhands-runtime/litellm-venv

if [[ "${SKILL_REVISE_CLAUDE_OPUS47_PREFLIGHT:-1}" == "1" ]]; then
  echo "[Preflight] Verifying Tatu accepts Claude Opus 4.7 revision settings..."
  preflight_reply=""
  for preflight_attempt in 1 2 3; do
    if preflight_reply="$(printf 'Reply with exactly: READY' | "$METHOD_ROOT/.venv/bin/python" -m skillrevise.llm.command)" \
      && [[ -n "$preflight_reply" ]]; then
      break
    fi
    echo "[Preflight] Attempt $preflight_attempt/3 failed; retrying in 8 seconds..." >&2
    preflight_reply=""
    sleep 8
  done
  [[ -n "$preflight_reply" ]] || { echo "[Preflight] Empty model response." >&2; exit 2; }
  echo "[Preflight] Passed (received a non-empty response)."
fi
if [[ "${SKILL_REVISE_CLAUDE_OPUS47_PREFLIGHT_ONLY:-0}" == "1" ]]; then
  echo "Preflight-only mode complete; no benchmark rollout was started."
  exit 0
fi

if [[ "$DOCKER_READY" != "1" ]]; then
  echo "Docker is unavailable in WSL. Start Docker Desktop and enable Ubuntu integration before running rollouts." >&2
  exit 2
fi

"$METHOD_ROOT/scripts/bootstrap_unified_openhands_runtime_cache.sh"
"$METHOD_ROOT/scripts/patch_unified_egress_firewall_cap.sh"

# A small number of task directories can legitimately change after their
# original image was built (for example, a verifier-only repair). Seed a
# Claude-specific manifest from the completed 39-task cache, then let the
# canonical prebuilder retain every matching image and rebuild only changed
# tasks. This prevents the executor from silently using a stale image.
if [[ ! -s "$PREBUILT_IMAGES" ]]; then
  mkdir -p "$(dirname "$PREBUILT_IMAGES")"
  cp "$PREBUILT_IMAGE_SEED" "$PREBUILT_IMAGES"
fi
echo "[Environment] Validating Claude prebuilt images; changed tasks will rebuild once..."
"$METHOD_ROOT/.venv/bin/python" "$METHOD_ROOT/scripts/prebuild_unified_core25_images.py" \
  --tasks-root "$TASKS_ROOT" \
  --task-manifest "$SOURCE_MANIFEST" \
  --output "$PREBUILT_IMAGES" \
  --attempts "${SKILL_REVISE_CLAUDE_OPUS47_PREBUILD_ATTEMPTS:-1}" \
  --retry-delay-seconds 20

# The full Fail-39 condition defers the expensive Civ6 task to the end.  A
# prefix-only recovery manifest intentionally does not contain Civ6, in which
# case preserve its supplied order instead of treating the absent task as an
# error.
if "$METHOD_ROOT/.venv/bin/python" -c '
import json, sys
tasks = json.load(open(sys.argv[1], encoding="utf-8")).get("tasks", [])
raise SystemExit(0 if any(t.get("task_id") == "civ6-adjacency-optimizer" for t in tasks) else 1)
' "$SOURCE_MANIFEST"; then
  "$METHOD_ROOT/.venv/bin/python" "$METHOD_ROOT/scripts/reorder_manifest_task_last.py" \
    "$SOURCE_MANIFEST" "$MANIFEST" civ6-adjacency-optimizer
else
  cp "$SOURCE_MANIFEST" "$MANIFEST"
  echo "Civ6 is absent from this manifest; preserving supplied task order: $MANIFEST"
fi

mkdir -p "$RESULTS_ROOT" "$JOBS_ROOT" "$CANDIDATES_ROOT"

# A verifier-only retry can turn an otherwise completed same-model No-Skill
# baseline into the valid 39/39 record without repeating 39 expensive agent
# rollouts.  Seed a fresh method label with that immutable merged baseline.
# Existing result files always win, so this never overwrites evidence.
REUSE_BASELINE="${SKILL_REVISE_CLAUDE_OPUS47_REUSE_BASELINE:-}"
if [[ -n "$REUSE_BASELINE" && ! -s "$RESULTS_ROOT/no_skill.json" ]]; then
  [[ -s "$REUSE_BASELINE" ]] || { echo "Reusable baseline is missing or empty: $REUSE_BASELINE" >&2; exit 2; }
  "$METHOD_ROOT/.venv/bin/python" scripts/reconcile_unified_baseline.py pending \
    "$REUSE_BASELINE" --output "$RESULTS_ROOT/.reused_baseline_pending.txt" >/dev/null
  if [[ -s "$RESULTS_ROOT/.reused_baseline_pending.txt" ]]; then
    echo "Reusable baseline still contains infrastructure errors: $REUSE_BASELINE" >&2
    exit 2
  fi
  cp "$REUSE_BASELINE" "$RESULTS_ROOT/no_skill.json"
  reuse_summary="${REUSE_BASELINE%.json}_summary.json"
  if [[ -s "$reuse_summary" ]]; then
    cp "$reuse_summary" "$RESULTS_ROOT/no_skill_summary.json"
  fi
  echo "[No Skill] Reused validated 39/39 baseline: $REUSE_BASELINE"
fi

# Preserve the controller traceback or terminal exit message.  Rollout-level
# artifacts describe completed tasks, but an interruption between tasks would
# otherwise leave no record explaining why the outer 39-task process stopped.
if [[ "${SKILL_REVISE_CLAUDE_OPUS47_CAPTURE_LOG:-1}" == "1" ]]; then
  exec > >(tee -a "$RESULTS_ROOT/launcher.log") 2>&1
fi

COMMON=(
  "$MANIFEST"
  --manifest-kind skillsbench
  --preserve-manifest-order
  --workspace-root "$METHOD_ROOT"
  --unified-tasks-root "$TASKS_ROOT"
  --unified-jobs-root "$JOBS_ROOT"
  --unified-candidates-root "$CANDIDATES_ROOT"
  --unified-model "$BENCHMARK_MODEL"
  --unified-verifier-proxy-mode "$VERIFIER_PROXY_MODE"
  --unified-method-id "$METHOD_ID"
  --unified-prebuilt-images "$PREBUILT_IMAGES"
)

run_if_missing() {
  local name="$1"
  local result="$2"
  shift 2
  if [[ -s "$result" ]]; then
    echo "[$name] Existing result found; skipping: $result"
    return 0
  fi
  echo "[$name] Starting 39-task run with $BENCHMARK_MODEL (native Claude default effort; ACP effort option omitted)"
  "$METHOD_ROOT/.venv/bin/python" -m skillrevise.cli "${COMMON[@]}" "$@"
}

run_if_missing "No Skill" "$RESULTS_ROOT/no_skill.json" \
  --baseline-only \
  --output "$RESULTS_ROOT/no_skill.json" \
  --summary-output "$RESULTS_ROOT/no_skill_summary.json"

run_if_missing "SkillRevise" "$RESULTS_ROOT/skillrevise_bundle.json" \
  --unified-skill-bundle-mode replace-original \
  --unified-bundle-repair \
  --unified-bundle-initial-traces "$PUBLISHED_ORIGINAL_TRACES" \
  --unified-bundle-max-targets 3 \
  --unified-bundle-accept-non-degrading \
  --paper-protocol \
  --author-mode template \
  --diagnosis-mode llm \
  --revision-mode llm-principle-bank \
  --principle-retrieval "$SKILL_REVISE_FAIL39_PRINCIPLE_RETRIEVAL" \
  --principle-embedding-model "$SKILL_REVISE_PRINCIPLE_EMBEDDING_MODEL" \
  --max-revisions 3 \
  --llm-command ".venv/bin/python -m skillrevise.llm.command" \
  --strict-llm \
  --output "$RESULTS_ROOT/skillrevise_bundle.json" \
  --summary-output "$RESULTS_ROOT/skillrevise_bundle_summary.json"

echo "Complete. Results: $RESULTS_ROOT"
