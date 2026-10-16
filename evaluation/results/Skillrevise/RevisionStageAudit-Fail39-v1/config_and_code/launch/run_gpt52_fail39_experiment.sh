#!/usr/bin/env bash
# Run No-Skill and bundle-aware SkillRevise on the 39 tasks that failed in the
# published GPT-5.2 Original-Skill representative trajectories.
#
# This script deliberately reuses the existing Tatu Cloud endpoint and key.
# It overrides only model identifiers: the sandbox rollout uses vllm/gpt-5.2
# and the SkillRevise author/diagnosis/revision command uses gpt-5.2.

set -euo pipefail

METHOD_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_LABEL="${SKILL_REVISE_FAIL39_RUN_LABEL:-tatu-gpt52-fail39-published-trace-r1}"
METHOD_ID="${SKILL_REVISE_FAIL39_METHOD_ID:-skillrevise-bundle-gpt52-fail39-published-trace-top3-r1}"
TASKS_ROOT="${SKILL_REVISE_UNIFIED_TASKS_ROOT:-$HOME/skillsbench-unified-overlay-gpt52fail39/tasks}"
SOURCE_MANIFEST="$METHOD_ROOT/manifests/gpt52-representative-fail39-latest_tasks.json"
MANIFEST="${SKILL_REVISE_FAIL39_MANIFEST:-$METHOD_ROOT/manifests/gpt52-representative-fail39-civ6-last_tasks.json}"
PREBUILT_IMAGES="$METHOD_ROOT/runs/unified/gpt52-representative-fail39-latest/prebuilt_images.json"
RESULTS_ROOT="$METHOD_ROOT/runs/unified/$RUN_LABEL"
JOBS_ROOT="$HOME/benchmark-jobs/$RUN_LABEL"
CANDIDATES_ROOT="$HOME/benchmark-candidates/$RUN_LABEL"
PUBLISHED_ORIGINAL_TRACES="${SKILL_REVISE_FAIL39_PUBLISHED_ORIGINAL_TRACES:-$METHOD_ROOT/runs/framework-backups/20260920/evaluation-results/GPT52-AllTasks-RepresentativeRuns-20260916}"
NO_SKILL_SOURCE="${SKILL_REVISE_FAIL39_NO_SKILL_SOURCE:-$METHOD_ROOT/runs/unified/tatu-gpt52-fail39-r3/no_skill.json}"

cd "$METHOD_ROOT"
# shellcheck disable=SC1091
source .env.unified.local

if [[ -z "${TATU_API_KEY:-}" || "$TATU_API_KEY" == '<PASTE_TATU_CLOUD_API_KEY_HERE>' ]]; then
  echo "Set TATU_API_KEY in $METHOD_ROOT/.env.unified.local first." >&2
  exit 2
fi
for required_path in "$TASKS_ROOT" "$SOURCE_MANIFEST" "$PREBUILT_IMAGES" "$PUBLISHED_ORIGINAL_TRACES"; do
  [[ -e "$required_path" ]] || { echo "Missing required path: $required_path" >&2; exit 2; }
done
"$METHOD_ROOT/.venv/bin/python" "$METHOD_ROOT/scripts/reorder_manifest_task_last.py" \
  "$SOURCE_MANIFEST" "$MANIFEST" civ6-adjacency-optimizer
docker info >/dev/null 2>&1 || {
  echo "Docker is unavailable in WSL. Start Docker Desktop and enable Ubuntu integration." >&2
  exit 2
}

# Keep the established Tatu Cloud API endpoint and credentials. Only change
# model names for this representative GPT-5.2 experiment.
export BENCHMARK_MODEL="${SKILL_REVISE_FAIL39_MODEL:-vllm/gpt-5.2}"
export SKILL_REVISE_REVISION_LLM_MODEL="${SKILL_REVISE_FAIL39_REVISION_MODEL:-gpt-5.2}"
# Dense retrieval depends on a separate embedding endpoint.  The Tatu Cloud
# rollout endpoint is sufficient for GPT-5.2 completion calls, but it does
# not guarantee that this optional endpoint is reachable from WSL.  BM25 is
# fully local and keeps the repair run reproducible when that service is down.
# Set SKILL_REVISE_FAIL39_PRINCIPLE_RETRIEVAL=hybrid-rrf explicitly only when
# the embedding endpoint and cache have been verified.
export SKILL_REVISE_FAIL39_PRINCIPLE_RETRIEVAL="${SKILL_REVISE_FAIL39_PRINCIPLE_RETRIEVAL:-bm25}"
export OPENAI_BASE_URL="${OPENAI_BASE_URL:-${BENCHFLOW_PROVIDER_BASE_URL:-}}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-${TATU_API_KEY}}"
# WSL inherits a Windows-local 127.0.0.1:7890 proxy in this environment.
# The direct SkillRevise command cannot safely use that proxy, whereas the
# sandbox LiteLLM route is configured separately below. Bypass it only for
# the direct author/selection/diagnosis/revision requests to Tatu Cloud.
export SKILL_REVISE_BYPASS_PROXY=1
export SKILL_REVISE_REVISION_LLM_HTTP_RETRY_ATTEMPTS="${SKILL_REVISE_FAIL39_LLM_RETRY_ATTEMPTS:-6}"
export SKILL_REVISE_REVISION_LLM_HTTP_RETRY_BASE_DELAY_SECONDS="${SKILL_REVISE_FAIL39_LLM_RETRY_DELAY_SECONDS:-3}"

# Reuse the already warmed OpenHands/LiteLLM runtime rather than attempting a
# network installation in each task container. v2 uses a GLIBC 2.31-compatible
# Python/LiteLLM stack; v1's cryptography wheel requires GLIBC 2.33 and fails
# in older SkillsBench task images.
export BENCHFLOW_OPENHANDS_RUNTIME_VOLUME=benchflow-openhands-runtime-v2-glibc231
export BENCHFLOW_FORCE_SANDBOX_LITELLM=1
export BENCHFLOW_SANDBOX_LITELLM_VENV=/opt/benchflow/openhands-runtime/litellm-venv

mkdir -p "$RESULTS_ROOT" "$JOBS_ROOT" "$CANDIDATES_ROOT"
"$METHOD_ROOT/scripts/bootstrap_unified_openhands_runtime_cache.sh"
# The current unified framework enables an iptables-based no-web policy but
# its stock Docker compose template omits the capability iptables requires.
# Apply the narrowly scoped, idempotent compatibility patch before rollouts.
"$METHOD_ROOT/scripts/patch_unified_egress_firewall_cap.sh"

COMMON=(
  "$MANIFEST"
  --manifest-kind skillsbench
  --preserve-manifest-order
  --workspace-root "$METHOD_ROOT"
  --unified-tasks-root "$TASKS_ROOT"
  --unified-jobs-root "$JOBS_ROOT"
  --unified-candidates-root "$CANDIDATES_ROOT"
  --unified-model "$BENCHMARK_MODEL"
  --unified-method-id "$METHOD_ID"
  --unified-prebuilt-images "$PREBUILT_IMAGES"
)

if [[ -n "${BENCHMARK_REASONING_EFFORT:-}" ]]; then
  COMMON+=(--unified-reasoning-effort "$BENCHMARK_REASONING_EFFORT")
fi

run_if_missing() {
  local name="$1"
  local result="$2"
  shift 2
  if [[ -s "$result" ]]; then
    echo "[$name] Existing result found; skipping: $result"
    return 0
  fi
  echo "[$name] Starting 39-task run with $BENCHMARK_MODEL"
  "$METHOD_ROOT/.venv/bin/python" -m skillrevise.cli "${COMMON[@]}" "$@"
}

if [[ -s "$RESULTS_ROOT/no_skill.json" ]]; then
  echo "[No Skill] Existing result found; skipping: $RESULTS_ROOT/no_skill.json"
elif [[ -s "$NO_SKILL_SOURCE" ]]; then
  cp "$NO_SKILL_SOURCE" "$RESULTS_ROOT/no_skill.json"
  source_summary="${NO_SKILL_SOURCE%.json}_summary.json"
  if [[ -s "$source_summary" ]]; then
    cp "$source_summary" "$RESULTS_ROOT/no_skill_summary.json"
  fi
  echo "[No Skill] Reused completed baseline: $NO_SKILL_SOURCE"
else
  run_if_missing "No Skill" "$RESULTS_ROOT/no_skill.json" \
    --baseline-only \
    --output "$RESULTS_ROOT/no_skill.json" \
    --summary-output "$RESULTS_ROOT/no_skill_summary.json"
fi

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
