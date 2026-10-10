from __future__ import annotations

import argparse
import json
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

from skillrevise.core.agents import MockAgentAdapter
from skillrevise.core.env import get_env
from skillrevise.benchmarks.alfworld import ALFWorldTaskLoader
from skillrevise.method.authoring import (
    FileSkillAuthor,
    LLMSkillAuthor,
    NaiveSkillAuthoringPromptBuilder,
    PriorGuidedSkillAuthor,
    SkillCreatorPromptBuilder,
    SkillAuthoringPromptBuilder,
    TemplateSkillAuthor,
)
from skillrevise.core.artifacts import ArtifactStore
from skillrevise.method.diagnosis import HeuristicDiagnoser, LLMDiagnoser, NoOpDiagnoser
from skillrevise.core.io import load_tasks, to_jsonable, write_json
from skillrevise.llm import CommandLLMClient
from skillrevise.core.loop import HarnessLoop
from skillrevise.core.bundle_loop import BundleRepairLoop
from skillrevise.core.metrics import UTILITY_PRESETS, utility_weights_for_preset
from skillrevise.core.models import ExecutionTrace, TrajectoryEvent
from skillrevise.method.bundle_selection import LLMBundleSkillSelector
from skillrevise.method.principles import PrincipleAbsorber, PrincipleBank, PrincipleRetrievalConfig
from skillrevise.core.reporting import summarize_baseline_runs, summarize_results
from skillrevise.method.revision import (
    REVISION_ABLATIONS,
    FreeFormLLMRevisionEngine,
    HeuristicRevisionEngine,
    LLMRevisionEngine,
)
from skillrevise.core.runner import PairedRunner
from skillrevise.benchmarks.skilllearnbench import SkillLearnBenchTaskLoader
from skillrevise.benchmarks.skillsbench import SkillsBenchTaskLoader, build_family_index, select_sibling_tasks
from skillrevise.benchmarks.skillsbench_adapter import CommandAgentHarness, SkillsBenchAgentAdapter
from skillrevise.benchmarks.verifier import CommandVerifier
from skillrevise.benchmarks.unified_executor_adapter import (
    SkillBundleMaterializer,
    UnifiedBenchmarkAdapter,
    build_shared_executor,
)


def _filter_tasks(tasks, *, task_ids=None, families=None, limit=None):
    selected = list(tasks)
    if task_ids:
        wanted = set(task_ids)
        selected = [task for task in selected if task.task_id in wanted]
    if families:
        wanted_families = set(families)
        selected = [task for task in selected if task.family in wanted_families]
    if limit is not None:
        selected = selected[:limit]
    if not selected:
        raise SystemExit("No tasks selected after applying --task-id/--family/--limit filters.")
    return selected


def _apply_budget_override(tasks, budget_seconds: int | None):
    if budget_seconds is None:
        return list(tasks)
    updated = []
    for task in tasks:
        metadata = dict(task.metadata)
        metadata["timeout_seconds"] = budget_seconds
        metadata["budget_seconds"] = budget_seconds
        updated.append(replace(task, metadata=metadata))
    return updated


def _resolve_utility_weights(args: argparse.Namespace):
    weights = utility_weights_for_preset(args.utility_preset)
    overrides = {
        "alpha": args.utility_alpha,
        "beta": args.utility_beta,
        "gamma": args.utility_gamma,
        "lam": args.utility_lambda,
    }
    for field, value in overrides.items():
        if value is not None:
            setattr(weights, field, value)
    return weights


def _apply_ablation_condition(args: argparse.Namespace) -> None:
    condition = getattr(args, "ablation_condition", "full")
    if condition in {"no-principle-memory", "no-principle-memory-no-diagnosis"}:
        args.disable_principle_memory = True
    if condition in {"no-diagnosis", "no-principle-memory-no-diagnosis"}:
        args.diagnosis_mode = "none"


def _experiment_config(args: argparse.Namespace, weights) -> dict[str, Any]:
    principle_limit = args.principle_limit if args.principle_limit is not None else 4
    return {
        "ablation_condition": getattr(args, "ablation_condition", "full"),
        "utility_preset": args.utility_preset,
        "utility_weights": {
            "alpha": weights.alpha,
            "beta": weights.beta,
            "gamma": weights.gamma,
            "lambda": weights.lam,
        },
        "max_revisions": args.max_revisions,
        "paper_protocol": getattr(args, "paper_protocol", False),
        "continue_after_non_improving_revision": getattr(
            args,
            "continue_after_non_improving_revision",
            False,
        ),
        "max_heldout": args.max_heldout,
        "budget_seconds": args.budget_seconds,
        "repeat": args.repeat,
        "author_mode": args.author_mode,
        "authoring_principle_interface": getattr(args, "authoring_principle_interface", "legacy"),
        "diagnosis_mode": args.diagnosis_mode,
        "diagnosis_enabled": args.diagnosis_mode != "none",
        "revision_mode": args.revision_mode,
        "revision_ablation": getattr(args, "revision_ablation", "none"),
        "revision_removed_mechanism": {
            "none": "none",
            "no-execution-anchors": "execution anchors",
            "no-preserve-ledger": "preserve ledger",
        }.get(getattr(args, "revision_ablation", "none"), "unknown"),
        "principle_memory_enabled": not getattr(args, "disable_principle_memory", False),
        "principle_bank": args.principle_bank,
        "principle_limit": principle_limit,
        "principle_retrieval": getattr(args, "principle_retrieval", "hybrid-rrf"),
        "principle_embedding_model": getattr(args, "principle_embedding_model", "qwen/qwen3-embedding-4b"),
        "principle_embedding_url": getattr(args, "principle_embedding_url", None),
        "principle_embedding_cache": getattr(args, "principle_embedding_cache", None),
        "principle_keyword_weight": getattr(args, "principle_keyword_weight", 0.5),
        "principle_semantic_weight": getattr(args, "principle_semantic_weight", 0.5),
        "principle_rrf_k": getattr(args, "principle_rrf_k", 60),
        "principle_dense_content_weight": getattr(args, "principle_dense_content_weight", 0.05),
        "enable_principle_absorption": args.enable_principle_absorption,
        "principle_bank_output": args.principle_bank_output,
        "baseline_only": args.baseline_only,
        "initial_skill_only": getattr(args, "initial_skill_only", False),
        "baseline_run": args.baseline_run,
        "strict_llm": args.strict_llm,
        "initial_skill": args.initial_skill,
        "unified_executor": {
            "enabled": bool(getattr(args, "unified_tasks_root", None)),
            "tasks_root": getattr(args, "unified_tasks_root", None),
            "jobs_root": getattr(args, "unified_jobs_root", None),
            "model": getattr(args, "unified_model", None),
            "reasoning_effort": getattr(args, "unified_reasoning_effort", None),
            "method_id": getattr(args, "unified_method_id", None),
            "verifier_proxy_mode": getattr(args, "unified_verifier_proxy_mode", None),
            "prebuilt_images_manifest": getattr(args, "unified_prebuilt_images", None),
            "skill_bundle_mode": getattr(args, "unified_skill_bundle_mode", "replace-original"),
            "bundle_repair": bool(getattr(args, "unified_bundle_repair", False)),
            "bundle_max_targets": getattr(args, "unified_bundle_max_targets", None),
            "bundle_accept_non_degrading": bool(
                getattr(args, "unified_bundle_accept_non_degrading", False)
            ),
            "bundle_initial_traces": getattr(args, "unified_bundle_initial_traces", None),
        },
    }


def _parse_unified_skill_targets(values: list[str] | None) -> dict[str, str]:
    targets: dict[str, str] = {}
    for value in values or []:
        task_id, separator, relative_path = value.partition("=")
        if not separator or not task_id.strip() or not relative_path.strip():
            raise SystemExit(
                "--unified-skill-target must use task_id=relative/path/SKILL.md."
            )
        if task_id in targets:
            raise SystemExit(f"Duplicate --unified-skill-target for {task_id!r}.")
        targets[task_id] = relative_path
    return targets


def _load_baseline_trace_cache(path: str | Path) -> dict[str, ExecutionTrace]:
    payload = json.loads(Path(path).read_text())
    items = payload.get("baseline_results")
    if not isinstance(items, list):
        raise SystemExit("--baseline-run must point to a baseline-only run JSON containing baseline_results.")

    traces: dict[str, ExecutionTrace] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        trace_data = item.get("no_skill")
        if not isinstance(trace_data, dict):
            continue
        trace = _execution_trace_from_json(trace_data)
        traces[trace.task_id] = trace
    if not traces:
        raise SystemExit(f"No reusable no-skill traces found in --baseline-run {path}.")
    return traces


def _load_published_original_skill_trace_cache(path: str | Path) -> dict[str, ExecutionTrace]:
    """Load published representative Original-Skill rollouts without replaying them."""
    root = Path(path)
    tasks_root = root / "tasks" if (root / "tasks").is_dir() else root
    traces: dict[str, ExecutionTrace] = {}
    for selected_run in sorted(tasks_root.glob("*/selected_run")):
        task_id = selected_run.parent.name
        benchmark_path = selected_run / "benchmark_result.json"
        selection_path = selected_run.parent / "run_selection.json"
        metadata_path = benchmark_path if benchmark_path.is_file() else selection_path
        if not metadata_path.is_file():
            continue
        benchmark = json.loads(metadata_path.read_text(encoding="utf-8"))
        result_path = selected_run / "result.json"
        result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.is_file() else {}
        trajectory_path = selected_run / "trajectory" / "acp_trajectory.jsonl"
        events: list[TrajectoryEvent] = []
        if trajectory_path.is_file():
            for index, line in enumerate(trajectory_path.read_text(encoding="utf-8").splitlines()):
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                text = event.get("text") or event.get("title") or event.get("content") or ""
                events.append(
                    TrajectoryEvent(
                        step_index=index,
                        kind=str(event.get("type", "unknown")),
                        summary=str(text)[:2000],
                        evidence=str(text)[:6000],
                        metadata={"published_event": True},
                    )
                )
        agent_result = result.get("agent_result") if isinstance(result.get("agent_result"), dict) else {}
        rewards = result.get("rewards") if isinstance(result.get("rewards"), dict) else {}
        reward = benchmark.get("reward")
        if reward is None:
            reward = rewards.get("reward")
        task_passed = bool(benchmark.get("task_passed", False))
        trace = ExecutionTrace(
            run_id=str(benchmark.get("rollout_id", result.get("rollout_name", task_id))),
            task_id=task_id,
            skill_version="published-original-skill",
            success=task_passed,
            status="success" if task_passed else "failure",
            started_at=str(result.get("started_at", "")),
            ended_at=str(result.get("finished_at", "")),
            tokens=int(agent_result.get("total_tokens", 0) or 0),
            tool_calls=int(result.get("n_tool_calls", agent_result.get("n_tool_calls", 0)) or 0),
            steps=int((result.get("trajectory_summary") or {}).get("steps", 0) or 0),
            latency_seconds=float(benchmark.get("wall_time_sec", 0.0) or 0.0),
            outcome_summary=(
                f"Published representative Original-Skill rollout: reward={reward}; "
                f"termination={benchmark.get('termination_reason', '')}; "
                f"verifier_error={benchmark.get('verifier_error') or 'none'}"
            ),
            events=events,
            metadata={
                "reward": reward,
                "published_representative": True,
                "published_benchmark_result": str(metadata_path),
                "published_trajectory": str(trajectory_path),
                "source_model": benchmark.get("model"),
                "source_provider": benchmark.get("provider_route"),
                "execution_ok": benchmark.get("execution_ok"),
                "protocol_evidence_valid": benchmark.get("protocol_evidence_valid"),
            },
        )
        traces[task_id] = trace
    if not traces:
        raise SystemExit(
            "--unified-bundle-initial-traces must point to a published results directory containing "
            "tasks/<task_id>/selected_run/benchmark_result.json."
        )
    return traces


def _execution_trace_from_json(data: dict[str, Any]) -> ExecutionTrace:
    return ExecutionTrace(
        run_id=str(data.get("run_id", "")),
        task_id=str(data["task_id"]),
        skill_version=data.get("skill_version"),
        success=bool(data.get("success", False)),
        status=str(data.get("status", "unknown")),
        started_at=str(data.get("started_at", "")),
        ended_at=str(data.get("ended_at", "")),
        tokens=int(data.get("tokens", 0) or 0),
        tool_calls=int(data.get("tool_calls", 0) or 0),
        steps=int(data.get("steps", 0) or 0),
        latency_seconds=float(data.get("latency_seconds", 0.0) or 0.0),
        outcome_summary=str(data.get("outcome_summary", "")),
        events=[_trajectory_event_from_json(event) for event in data.get("events", []) if isinstance(event, dict)],
        metadata=dict(data.get("metadata", {})),
    )


def _trajectory_event_from_json(data: dict[str, Any]) -> TrajectoryEvent:
    return TrajectoryEvent(
        step_index=int(data.get("step_index", 0) or 0),
        kind=str(data.get("kind", "unknown")),
        summary=str(data.get("summary", "")),
        evidence=str(data.get("evidence", "")),
        metadata=dict(data.get("metadata", {})),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SkillRevise skill generation, diagnosis, and revision.")
    parser.add_argument("tasks", help="Path to a JSON file containing task specs.")
    parser.add_argument("--output", default="skillrevise_run.json", help="Where to save the run artifact.")
    parser.add_argument("--summary-output", help="Optional path for a compact summary JSON artifact.")
    parser.add_argument("--task-id", action="append", help="Run only the given task id. Can be repeated.")
    parser.add_argument("--family", action="append", help="Run only tasks from the given family. Can be repeated.")
    parser.add_argument("--limit", type=int, help="Run at most this many tasks after filtering.")
    parser.add_argument("--max-revisions", type=int, default=1, help="Maximum number of revise/re-evaluate rounds.")
    parser.add_argument(
        "--paper-protocol",
        action="store_true",
        help=(
            "Use the original SkillRevise per-task protocol: No Skill is a separate baseline, "
            "only failed v0/v1/v2 candidates are diagnosed and revised, and a verifier-passing "
            "candidate stops the chain."
        ),
    )
    parser.add_argument(
        "--continue-after-non-improving-revision",
        action="store_true",
        help=(
            "Exploration mode: continue revising from a candidate even when it does "
            "not beat the incumbent; final selection still uses the best utility."
        ),
    )
    parser.add_argument("--repeat", type=int, default=1, help="Repeat each selected task this many times.")
    parser.add_argument("--budget-seconds", type=int, help="Override each task timeout/budget in seconds.")
    parser.add_argument(
        "--baseline-only",
        action="store_true",
        help="Run only the no-skill baseline for each selected task and skip skill generation/revision.",
    )
    parser.add_argument(
        "--baseline-run",
        help="Reuse no-skill traces from a previous baseline-only run JSON instead of rerunning them.",
    )
    parser.add_argument(
        "--initial-skill-only",
        action="store_true",
        help="Run each task once with --initial-skill and skip the no-skill comparison, diagnosis, and revision.",
    )
    parser.add_argument(
        "--original-skill-only",
        action="store_true",
        help=(
            "Run only each task's official environment/skills bundle through the shared "
            "benchmark executor. Requires --unified-tasks-root."
        ),
    )
    parser.add_argument(
        "--utility-preset",
        choices=tuple(sorted(UTILITY_PRESETS)),
        default="full",
        help="Utility weighting preset for selection and reporting.",
    )
    parser.add_argument("--utility-alpha", type=float, help="Override same-task reward/success gain weight.")
    parser.add_argument("--utility-beta", type=float, help="Override efficiency gain weight.")
    parser.add_argument("--utility-gamma", type=float, help="Override transfer gain weight.")
    parser.add_argument("--utility-lambda", type=float, help="Override interference penalty weight.")
    parser.add_argument(
        "--manifest-kind",
        choices=("generic", "skillsbench", "skilllearnbench", "alfworld"),
        default="generic",
        help="How to interpret the task manifest.",
    )
    parser.add_argument(
        "--preserve-manifest-order",
        action="store_true",
        help="For a SkillsBench manifest, execute entries in JSON order instead of sorting by task id.",
    )
    parser.add_argument("--workspace-root", help="Workspace root used to resolve relative repo paths.")
    parser.add_argument("--harness-command", help="External harness command for real benchmark execution.")
    parser.add_argument("--verifier-command", help="Optional verifier command override.")
    parser.add_argument(
        "--disable-verifier",
        action="store_true",
        help="Use harness status directly and skip the separate verifier step.",
    )
    parser.add_argument("--artifacts-root", help="Optional artifact directory for real benchmark runs.")
    parser.add_argument(
        "--unified-tasks-root",
        help=(
            "Root of the project-group frozen SkillsBench task checkout for the shared "
            "benchmark executor. Enables unified execution."
        ),
    )
    parser.add_argument(
        "--unified-jobs-root",
        help="Output root owned by the shared benchmark executor; rollout directories are never overwritten.",
    )
    parser.add_argument(
        "--unified-model",
        help="Pinned provider-qualified BenchFlow/LiteLLM model route for the shared executor.",
    )
    parser.add_argument(
        "--unified-reasoning-effort",
        help="Pinned reasoning effort passed to the shared executor instance.",
    )
    parser.add_argument(
        "--unified-verifier-proxy-mode",
        choices=("off", "inherit", "explicit"),
        help="Shared-executor verifier proxy policy. Omit to use its documented default (off).",
    )
    parser.add_argument(
        "--unified-candidates-root",
        help=(
            "Where immutable full-skill candidate bundles are written. Required with "
            "--unified-tasks-root."
        ),
    )
    parser.add_argument(
        "--unified-method-id",
        default="skillrevise",
        help="Safe method identifier recorded by the shared executor (default: skillrevise).",
    )
    parser.add_argument(
        "--unified-prebuilt-images",
        help=(
            "Path to a frozen image manifest generated by "
            "scripts/prebuild_unified_core25_images.py. The unified executor then "
            "uses fresh containers from those images and preserves the images at teardown."
        ),
    )
    parser.add_argument(
        "--unified-skill-target",
        action="append",
        help=(
            "Target official Skill to revise, as task_id=relative/path/SKILL.md. "
            "Required only for tasks containing multiple SKILL.md files. Can be repeated."
        ),
    )
    parser.add_argument(
        "--unified-skill-bundle-mode",
        choices=("replace-original", "generated-only"),
        default="replace-original",
        help=(
            "How a unified method-skill bundle is built. replace-original preserves the official "
            "bundle and replaces one selected SKILL.md; generated-only injects only the LLM-authored "
            "SkillRevise Skill and never reads benchmark-provided Skills."
        ),
    )
    parser.add_argument(
        "--unified-bundle-repair",
        action="store_true",
        help=(
            "Bundle-level extension: use an LLM to rank official SKILL.md files, then run the "
            "single-Skill SkillRevise loop on each selected file while freezing all others."
        ),
    )
    parser.add_argument(
        "--unified-bundle-initial-traces",
        help=(
            "Published representative Original-Skill results directory. When supplied with "
            "--unified-bundle-repair, its frozen failed trajectories are used for target selection "
            "and diagnosis; Original Skill and unmodified v0 are never replayed locally."
        ),
    )
    parser.add_argument(
        "--unified-bundle-max-targets",
        type=int,
        default=2,
        help="Maximum LLM-selected official Skills explored by --unified-bundle-repair (default: 2).",
    )
    parser.add_argument(
        "--unified-bundle-accept-non-degrading",
        action="store_true",
        help=(
            "Retain an equal-reward intermediate revision before repairing the next candidate. "
            "Use only for separately reported multi-Skill binary-reward experiments."
        ),
    )
    parser.add_argument("--max-heldout", type=int, default=None, help="Maximum number of sibling tasks used for transfer.")
    parser.add_argument(
        "--author-mode",
        choices=(
            "template",
            "prior",
            "llm",
            "llm-principle",
            "llm-principle-bank",
            "llm-naive",
            "llm-skill-creator",
        ),
        default="template",
        help="How to generate the initial skill.",
    )
    parser.add_argument(
        "--ablation-condition",
        choices=("full", "no-principle-memory", "no-diagnosis", "no-principle-memory-no-diagnosis"),
        default="full",
        help=(
            "Convenience 2x2 ablation switch. full keeps principle memory and diagnosis; "
            "no-principle-memory disables principle-bank retrieval/absorption in authoring and revision; "
            "no-diagnosis withholds diagnosis while still allowing revision; the combined condition disables both."
        ),
    )
    parser.add_argument(
        "--diagnosis-mode",
        choices=("heuristic", "llm", "none"),
        default="heuristic",
        help="How to diagnose skill failures.",
    )
    parser.add_argument(
        "--authoring-principle-interface",
        choices=("legacy", "action-map"),
        default=get_env(os.environ, "SKILL_REVISE_AUTHORING_PRINCIPLE_INTERFACE", "legacy"),
        help=(
            "How v0 direct skill authoring turns retrieved principles into the initial skill. "
            "Use legacy to restore the previous prompt behavior."
        ),
    )
    parser.add_argument(
        "--revision-mode",
        choices=("heuristic", "llm", "llm-structured", "llm-principle-bank", "llm-freeform"),
        default="heuristic",
        help="How to revise skills.",
    )
    parser.add_argument(
        "--revision-ablation",
        choices=tuple(sorted(REVISION_ABLATIONS)),
        default="none",
        help=(
            "Structured-revision ablation switch. no-execution-anchors removes execution-anchor "
            "requirements and trace fields; no-preserve-ledger removes preserve ledger/risk fields."
        ),
    )
    parser.add_argument("--principle-bank", help="Optional JSON repair-principle bank for structured LLM revision.")
    parser.add_argument(
        "--principle-limit",
        type=int,
        help="Maximum number of retrieved repair principles injected into structured LLM revision.",
    )
    parser.add_argument(
        "--principle-retrieval",
        choices=("legacy", "bm25", "dense", "hybrid-rrf"),
        default="hybrid-rrf",
        help=(
            "Principle-bank retrieval backend. hybrid-rrf follows the SkillsBench-style "
            "BM25 + dense embedding + reciprocal-rank-fusion setup."
        ),
    )
    parser.add_argument(
        "--principle-embedding-model",
        default=get_env(os.environ, "SKILL_REVISE_PRINCIPLE_EMBEDDING_MODEL") or "qwen/qwen3-embedding-4b",
        help=(
            "Embedding model name used by dense/hybrid principle retrieval. Defaults to "
            "SKILL_REVISE_PRINCIPLE_EMBEDDING_MODEL when set."
        ),
    )
    parser.add_argument(
        "--principle-embedding-url",
        help=(
            "OpenAI-compatible embeddings endpoint or base URL. If omitted, dense retrieval "
            "uses SKILL_REVISE_PRINCIPLE_EMBEDDING_URL from the environment or local config."
        ),
    )
    parser.add_argument(
        "--principle-embedding-cache",
        help="Optional JSON cache file for principle/query embeddings.",
    )
    parser.add_argument("--principle-keyword-weight", type=float, default=0.5, help="RRF weight for BM25 retrieval.")
    parser.add_argument(
        "--principle-semantic-weight",
        type=float,
        default=0.5,
        help="RRF weight for dense embedding retrieval.",
    )
    parser.add_argument("--principle-rrf-k", type=int, default=60, help="RRF fusion constant.")
    parser.add_argument(
        "--principle-dense-content-weight",
        type=float,
        default=0.05,
        help="Dense retrieval weight for full principle content versus metadata.",
    )
    parser.add_argument(
        "--enable-principle-absorption",
        action="store_true",
        help="Absorb outcome-improving, utility-positive revision experience back into the principle bank.",
    )
    parser.add_argument(
        "--disable-principle-memory",
        action="store_true",
        help=(
            "Ablation switch: do not inject retrieved principle-bank entries into v0 authoring or revision, "
            "and do not absorb new principles."
        ),
    )
    parser.add_argument(
        "--principle-bank-output",
        help="Optional path to write the updated principle bank after absorption.",
    )
    parser.add_argument("--llm-command", help="External LLM command that reads prompt from stdin and writes response to stdout.")
    parser.add_argument("--llm-timeout", type=int, default=600, help="Timeout for each LLM command call.")
    parser.add_argument("--initial-skill", help="Optional Markdown skill file to use as the initial skill.")
    parser.add_argument(
        "--initial-skill-version",
        default="v0",
        help="Version label to assign to --initial-skill before revision numbering continues.",
    )
    parser.add_argument(
        "--strict-llm",
        action="store_true",
        help="Fail instead of falling back to a heuristic skill when LLM skill authoring fails.",
    )
    args = parser.parse_args()
    _apply_ablation_condition(args)

    unified_required = (
        args.unified_tasks_root,
        args.unified_jobs_root,
        args.unified_model,
        args.unified_candidates_root,
    )
    unified_enabled = any(value is not None for value in unified_required)
    if unified_enabled and not all(unified_required):
        parser.error(
            "Unified execution requires --unified-tasks-root, --unified-jobs-root, "
            "--unified-model, and --unified-candidates-root together."
        )
    if unified_enabled and args.harness_command:
        parser.error("--harness-command cannot be used with the shared benchmark executor.")
    if unified_enabled and (args.verifier_command or args.disable_verifier):
        parser.error(
            "The shared benchmark executor owns verification; do not pass "
            "--verifier-command or --disable-verifier."
        )
    if args.original_skill_only and not unified_enabled:
        parser.error("--original-skill-only requires the shared benchmark executor options.")
    if sum(bool(value) for value in (args.baseline_only, args.initial_skill_only, args.original_skill_only)) > 1:
        parser.error("Only one of --baseline-only, --initial-skill-only, and --original-skill-only may be used.")
    if args.paper_protocol and args.baseline_run:
        parser.error("--paper-protocol keeps No Skill outside the revision trajectory; omit --baseline-run.")
    if args.paper_protocol and args.continue_after_non_improving_revision:
        parser.error("--paper-protocol is failure-conditioned; omit --continue-after-non-improving-revision.")
    if args.unified_skill_bundle_mode == "generated-only" and args.unified_skill_target:
        parser.error("--unified-skill-target is only valid with --unified-skill-bundle-mode replace-original.")
    if args.unified_bundle_repair and not unified_enabled:
        parser.error("--unified-bundle-repair requires the shared unified executor options.")
    if args.unified_bundle_repair and args.unified_skill_bundle_mode != "replace-original":
        parser.error("--unified-bundle-repair requires --unified-skill-bundle-mode replace-original.")
    if args.unified_bundle_repair and args.unified_skill_target:
        parser.error("--unified-bundle-repair selects targets dynamically; omit --unified-skill-target.")
    if args.unified_bundle_initial_traces and not args.unified_bundle_repair:
        parser.error("--unified-bundle-initial-traces requires --unified-bundle-repair.")
    if args.unified_bundle_max_targets < 1:
        parser.error("--unified-bundle-max-targets must be >= 1.")
    if unified_enabled and args.repeat != 1:
        parser.error(
            "The shared executor records one immutable rollout per call. Run repeats as "
            "separate invocations with separate jobs roots instead of --repeat."
        )
    if unified_enabled and args.max_heldout is not None:
        parser.error(
            "Transfer evaluation is not part of the shared single-rollout protocol; omit --max-heldout."
        )
    if unified_enabled and args.utility_preset != "success-only":
        print("Unified execution uses success-only selection because the public executor does not guarantee token totals.")
        args.utility_preset = "success-only"

    if args.manifest_kind == "skillsbench":
        tasks = SkillsBenchTaskLoader(
            args.workspace_root,
            preserve_manifest_order=args.preserve_manifest_order,
        ).load(args.tasks)
    elif args.manifest_kind == "skilllearnbench":
        tasks = SkillLearnBenchTaskLoader(args.workspace_root).load(args.tasks)
    elif args.manifest_kind == "alfworld":
        tasks = ALFWorldTaskLoader(args.workspace_root).load(args.tasks)
    else:
        tasks = load_tasks(args.tasks)
    tasks = _filter_tasks(tasks, task_ids=args.task_id, families=args.family, limit=args.limit)
    tasks = _apply_budget_override(tasks, args.budget_seconds)
    if args.repeat < 1:
        parser.error("--repeat must be >= 1")
    families = build_family_index(tasks)
    weights = _resolve_utility_weights(args)
    experiment_config = _experiment_config(args, weights)

    if unified_enabled:
        executor = build_shared_executor(
            tasks_root=args.unified_tasks_root,
            jobs_root=args.unified_jobs_root,
            model=args.unified_model,
            reasoning_effort=args.unified_reasoning_effort,
            verifier_proxy_mode=args.unified_verifier_proxy_mode,
            prebuilt_images_manifest=args.unified_prebuilt_images,
        )
        bundle_materializer = SkillBundleMaterializer(
            tasks_root=args.unified_tasks_root,
            candidates_root=args.unified_candidates_root,
            target_skill_by_task=_parse_unified_skill_targets(args.unified_skill_target),
            bundle_mode=args.unified_skill_bundle_mode,
        )
        if not (
            args.baseline_only
            or args.original_skill_only
            or args.initial_skill_only
            or args.initial_skill
            or args.unified_bundle_repair
        ) and args.unified_skill_bundle_mode == "replace-original":
            # A unified method-skill bundle replaces a concrete official
            # SKILL.md. Give the author that exact frozen source rather than
            # asking it to invent an unrelated standalone skill from the task
            # prompt alone.
            tasks = [bundle_materializer.with_original_skill_context(task) for task in tasks]
        adapter = UnifiedBenchmarkAdapter(
            executor=executor,
            bundle_materializer=bundle_materializer,
            method_id=args.unified_method_id,
        )
    elif args.harness_command:
        artifact_store = ArtifactStore(args.artifacts_root) if args.artifacts_root else None
        verifier = CommandVerifier(args.verifier_command) if args.verifier_command else None
        adapter = SkillsBenchAgentAdapter(
            harness=CommandAgentHarness(args.harness_command),
            artifact_store=artifact_store,
            verifier=verifier,
            disable_verifier=args.disable_verifier,
        )
    else:
        adapter = MockAgentAdapter()

    if args.original_skill_only:
        if not isinstance(adapter, UnifiedBenchmarkAdapter):
            raise AssertionError("validated above")
        original_items = []
        for task in tasks:
            trace = adapter.run_original_skill(task)
            original_items.append((task, trace))
            print(
                f"{task.task_id}: original-skill success={trace.success} "
                f"reward={trace.metadata.get('reward')} comparable={trace.metadata.get('comparable')}"
            )
        rewards = [trace.metadata.get("reward") for _, trace in original_items]
        numeric_rewards = [float(reward) for reward in rewards if isinstance(reward, (int, float))]
        summary = {
            "num_runs": len(original_items),
            "num_comparable": sum(1 for _, trace in original_items if trace.metadata.get("comparable") is True),
            "num_successes": sum(1 for _, trace in original_items if trace.success),
            "mean_reward": sum(numeric_rewards) / len(numeric_rewards) if numeric_rewards else None,
        }
        write_json(
            args.output,
            {
                "experiment_config": experiment_config,
                "summary": summary,
                "original_skill_results": [
                    {"task": to_jsonable(task), "original_skill": to_jsonable(trace)}
                    for task, trace in original_items
                ],
            },
        )
        if args.summary_output:
            write_json(args.summary_output, summary)
        print(f"Wrote {len(original_items)} original-Skill task reports to {args.output}")
        return

    if args.baseline_only:
        baseline_items = []
        for repeat_index in range(args.repeat):
            for task in tasks:
                trace = adapter.run(task, None)
                trace.metadata["repeat_index"] = repeat_index
                baseline_items.append((task, trace))
                summary = summarize_baseline_runs(baseline_items)
                write_json(
                    args.output,
                    {
                        "experiment_config": experiment_config,
                        "completed": False,
                        "num_completed": len(baseline_items),
                        "num_expected": len(tasks) * args.repeat,
                        "summary": summary,
                        "baseline_results": [
                            {"task": to_jsonable(item_task), "no_skill": to_jsonable(item_trace)}
                            for item_task, item_trace in baseline_items
                        ],
                    },
                )
                if args.summary_output:
                    write_json(args.summary_output, summary | {"completed": False})
                score = trace.metadata.get("reward")
                print(
                    f"{task.task_id}: repeat={repeat_index} "
                    f"no-skill success={trace.success} reward={score} status={trace.status}"
                )

        summary = summarize_baseline_runs(baseline_items)
        write_json(
            args.output,
            {
                "experiment_config": experiment_config,
                "completed": True,
                "num_completed": len(baseline_items),
                "num_expected": len(tasks) * args.repeat,
                "summary": summary,
                "baseline_results": [
                    {"task": to_jsonable(task), "no_skill": to_jsonable(trace)} for task, trace in baseline_items
                ],
            },
        )
        if args.summary_output:
            write_json(args.summary_output, summary | {"completed": True})
        print(f"Wrote {len(baseline_items)} baseline task reports to {args.output}")
        if args.summary_output:
            print(f"Wrote compact baseline summary to {args.summary_output}")
        return

    if args.initial_skill_only:
        if not args.initial_skill:
            parser.error("--initial-skill-only requires --initial-skill.")
        author = FileSkillAuthor(args.initial_skill, version=args.initial_skill_version)
        initial_skill_items = []
        for repeat_index in range(args.repeat):
            for task in tasks:
                skill = author.author(task)
                trace = adapter.run(task, skill)
                trace.metadata["repeat_index"] = repeat_index
                initial_skill_items.append((task, skill, trace))
                print(
                    f"{task.task_id}: repeat={repeat_index} initial-skill={skill.version} "
                    f"success={trace.success} reward={trace.metadata.get('reward')} status={trace.status}"
                )
        rewards = [item_trace.metadata.get("reward") for _, _, item_trace in initial_skill_items]
        numeric_rewards = [float(reward) for reward in rewards if isinstance(reward, (int, float))]
        summary = {
            "num_runs": len(initial_skill_items),
            "num_successes": sum(1 for _, _, trace in initial_skill_items if trace.success),
            "mean_reward": sum(numeric_rewards) / len(numeric_rewards) if numeric_rewards else None,
        }
        write_json(
            args.output,
            {
                "experiment_config": experiment_config,
                "summary": summary,
                "initial_skill_results": [
                    {"task": to_jsonable(task), "skill": to_jsonable(skill), "with_skill": to_jsonable(trace)}
                    for task, skill, trace in initial_skill_items
                ],
            },
        )
        if args.summary_output:
            write_json(args.summary_output, summary)
        print(f"Wrote {len(initial_skill_items)} initial-Skill task reports to {args.output}")
        if args.summary_output:
            print(f"Wrote compact initial-Skill summary to {args.summary_output}")
        return

    llm = CommandLLMClient(args.llm_command, timeout_seconds=args.llm_timeout) if args.llm_command else None
    if (
        args.author_mode
        in {"llm", "llm-principle", "llm-principle-bank", "llm-naive", "llm-skill-creator"}
        or args.diagnosis_mode == "llm"
        or args.revision_mode in {"llm", "llm-structured", "llm-principle-bank", "llm-freeform"}
        or args.unified_bundle_repair
    ) and llm is None:
        parser.error("--llm-command is required when any mode is set to llm")

    principle_path = args.principle_bank
    principle_limit = args.principle_limit if args.principle_limit is not None else 4
    principle_retrieval_config = PrincipleRetrievalConfig(
        method=args.principle_retrieval,
        embedding_model=args.principle_embedding_model,
        embedding_url=args.principle_embedding_url,
        embedding_cache=args.principle_embedding_cache,
        keyword_weight=args.principle_keyword_weight,
        semantic_weight=args.principle_semantic_weight,
        rrf_k=args.principle_rrf_k,
        dense_content_weight=args.principle_dense_content_weight,
    )
    principle_bank = (
        PrincipleBank.from_json(principle_path, retrieval_config=principle_retrieval_config)
        if principle_path
        else PrincipleBank.with_seed_principles(retrieval_config=principle_retrieval_config)
    )

    if args.initial_skill:
        author = FileSkillAuthor(args.initial_skill, version=args.initial_skill_version)
    elif args.author_mode in {"llm", "llm-principle", "llm-principle-bank"}:
        authoring_principle_bank = (
            principle_bank
            if args.author_mode == "llm-principle-bank" and not args.disable_principle_memory
            else None
        )
        author = LLMSkillAuthor(
            llm,
            prompt_builder=SkillAuthoringPromptBuilder(
                principle_bank=authoring_principle_bank,
                principle_limit=principle_limit,
                principle_interface=args.authoring_principle_interface,
            ),
            allow_fallback=not args.strict_llm,
        )  # type: ignore[arg-type]
    elif args.author_mode == "llm-naive":
        author = LLMSkillAuthor(
            llm,
            prompt_builder=NaiveSkillAuthoringPromptBuilder(),
            fallback_author=TemplateSkillAuthor(),
            allow_fallback=not args.strict_llm,
        )  # type: ignore[arg-type]
    elif args.author_mode == "llm-skill-creator":
        author = LLMSkillAuthor(
            llm,
            prompt_builder=SkillCreatorPromptBuilder(),
            fallback_author=TemplateSkillAuthor(),
            allow_fallback=not args.strict_llm,
        )  # type: ignore[arg-type]
    elif args.author_mode == "prior":
        author = PriorGuidedSkillAuthor()
    else:
        author = TemplateSkillAuthor()

    if args.diagnosis_mode == "llm":
        diagnoser = LLMDiagnoser(llm)  # type: ignore[arg-type]
    elif args.diagnosis_mode == "none":
        diagnoser = NoOpDiagnoser()
    else:
        diagnoser = HeuristicDiagnoser()
    if args.revision_mode == "llm-freeform":
        reviser = FreeFormLLMRevisionEngine(
            llm,
            allow_fallback=not args.strict_llm,
        )  # type: ignore[arg-type]
    elif args.revision_mode in {"llm", "llm-structured", "llm-principle-bank"}:
        reviser = LLMRevisionEngine(
            llm,
            principle_bank=principle_bank,
            principle_limit=principle_limit,
            allow_fallback=not args.strict_llm,
            use_principle_memory=not args.disable_principle_memory,
            revision_ablation=args.revision_ablation,
        )  # type: ignore[arg-type]
    else:
        reviser = HeuristicRevisionEngine()
    principle_absorber = (
        PrincipleAbsorber(principle_bank)
        if args.enable_principle_absorption and not args.disable_principle_memory
        else None
    )

    loop = HarnessLoop(
        author=author,
        runner=PairedRunner(
            adapter,
            weights=weights,
            baseline_traces=_load_baseline_trace_cache(args.baseline_run) if args.baseline_run else None,
            # The shared executor records one immutable rollout per invocation.
            # Infrastructure retries, if authorized by the study protocol, must
            # be separate, visible rollout IDs rather than hidden retries here.
            max_evaluation_attempts=1 if unified_enabled else None,
            paper_protocol=args.paper_protocol,
        ),
        diagnoser=diagnoser,
        reviser=reviser,
        max_revisions=args.max_revisions,
        principle_absorber=principle_absorber,
        continue_after_non_improving_revision=args.continue_after_non_improving_revision,
        require_diagnosis_for_revision=args.diagnosis_mode != "none",
        paper_protocol=args.paper_protocol,
    )

    if args.unified_bundle_repair:
        if not isinstance(adapter, UnifiedBenchmarkAdapter):
            raise AssertionError("validated above")
        if llm is None:  # pragma: no cover - validated above
            raise AssertionError("bundle target selection requires an LLM")
        published_initial_traces = (
            _load_published_original_skill_trace_cache(args.unified_bundle_initial_traces)
            if args.unified_bundle_initial_traces
            else {}
        )
        missing_published_traces = sorted(
            task.task_id for task in tasks if task.task_id not in published_initial_traces
        ) if args.unified_bundle_initial_traces else []
        if missing_published_traces:
            raise SystemExit(
                "Published initial traces are missing for selected tasks: "
                + ", ".join(missing_published_traces)
            )
        bundle_loop = BundleRepairLoop(
            loop=loop,
            adapter=adapter,
            materializer=adapter.bundle_materializer,
            selector=LLMBundleSkillSelector(llm, max_targets=args.unified_bundle_max_targets),
            accept_non_degrading=args.unified_bundle_accept_non_degrading,
            initial_traces=published_initial_traces,
        )
        bundle_results = []
        checkpoint_path = Path(args.output).with_name(
            f"{Path(args.output).stem}.partial.json"
        )

        def write_bundle_checkpoint() -> None:
            """Persist every completed bundle task before advancing the batch.

            Direct LLM diagnosis and revision text lives on the in-memory
            result objects.  A controller interruption must not reduce a
            completed prefix to rollout-only artifacts, which are
            insufficient for the Gold diagnosis evaluation.
            """
            valid_partial = [
                item
                for item in bundle_results
                if item.selected_trace
                and item.selected_trace.metadata.get("reward") is not None
            ]
            partial_successes = [
                item for item in bundle_results if item.selected_trace and item.selected_trace.success
            ]
            partial_rewards = [
                float(item.selected_trace.metadata["reward"])
                for item in valid_partial
                if isinstance(item.selected_trace.metadata.get("reward"), (int, float))
            ]
            write_json(
                checkpoint_path,
                {
                    "experiment_config": experiment_config,
                    "summary": {
                        "num_runs": len(bundle_results),
                        "num_valid_runs": len(valid_partial),
                        "num_successes": len(partial_successes),
                        "mean_reward": (
                            sum(partial_rewards) / len(partial_rewards)
                            if partial_rewards
                            else None
                        ),
                        "checkpoint": True,
                    },
                    "bundle_results": [to_jsonable(item) for item in bundle_results],
                },
            )
        for repeat_index in range(args.repeat):
            for task in tasks:
                result = bundle_loop.run_task(task)
                selected = result.selected_trace or result.initial_trace
                selected.metadata["repeat_index"] = repeat_index
                bundle_results.append(result)
                selected_targets = [] if result.selection is None else result.selection.targets
                print(
                    f"{task.task_id}: repeat={repeat_index} bundle-targets={selected_targets} "
                    f"accepted={[episode.target_skill for episode in result.episodes if episode.accepted]} "
                    f"score={selected.metadata.get('reward')} success={selected.success}"
                )
                write_bundle_checkpoint()
        valid = [item for item in bundle_results if item.selected_trace and item.selected_trace.metadata.get("reward") is not None]
        successes = [item for item in bundle_results if item.selected_trace and item.selected_trace.success]
        rewards = [
            float(item.selected_trace.metadata["reward"])
            for item in valid
            if isinstance(item.selected_trace.metadata.get("reward"), (int, float))
        ]
        summary = {
            "num_runs": len(bundle_results),
            "num_valid_runs": len(valid),
            "num_successes": len(successes),
            "mean_reward": sum(rewards) / len(rewards) if rewards else None,
            "protocol": "bundle-extension; target selection is reported separately from single-Skill SkillRevise",
        }
        write_json(
            args.output,
            {
                "experiment_config": experiment_config,
                "summary": summary,
                "bundle_results": [to_jsonable(item) for item in bundle_results],
            },
        )
        if args.summary_output:
            write_json(args.summary_output, summary)
        checkpoint_path.unlink(missing_ok=True)
        print(f"Wrote {len(bundle_results)} bundle-repair task reports to {args.output}")
        return

    results = []
    for repeat_index in range(args.repeat):
        for task in tasks:
            heldout = select_sibling_tasks(task, families, max_tasks=args.max_heldout)
            result = loop.run_task(task, heldout_tasks=heldout)
            result.selected_evaluation.with_skill.metadata["repeat_index"] = repeat_index
            result.selected_evaluation.no_skill.metadata["repeat_index"] = repeat_index
            results.append(result)
            print(
                f"{task.task_id}: repeat={repeat_index} selected {result.selected_skill.version} "
                f"score={result.selected_evaluation.utility.overall_score:.3f} "
                f"success={result.selected_evaluation.with_skill.success}"
            )

    summary = summarize_results(results)
    write_json(
        args.output,
        {
            "experiment_config": experiment_config,
            "summary": summary,
            "absorbed_principles": to_jsonable(loop.absorbed_principles),
            "results": [to_jsonable(result) for result in results],
        },
    )
    if args.summary_output:
        write_json(args.summary_output, summary)
    if args.principle_bank_output and not args.disable_principle_memory:
        principle_bank.write_json(args.principle_bank_output)
    print(f"Wrote {len(results)} task reports to {args.output}")
    if args.summary_output:
        print(f"Wrote compact summary to {args.summary_output}")
    if args.principle_bank_output and not args.disable_principle_memory:
        print(f"Wrote principle bank to {args.principle_bank_output}")


if __name__ == "__main__":
    main()
