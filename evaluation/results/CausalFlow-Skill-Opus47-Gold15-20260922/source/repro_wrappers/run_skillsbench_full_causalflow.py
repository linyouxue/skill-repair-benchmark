"""Run original CausalFlow CRS and repair on one failed SkillsBench rollout.

This is the formal adapter between a losslessly recorded SkillsBench terminal
trajectory and CausalFlow's original ``CausalAttribution`` /
``CounterfactualRepair`` classes.  Every intervention is evaluated in a fresh
task container with the official verifier.  The reexecutor uses the observed
file-resource graph to replay causal prerequisites, the replacement command,
and downstream consumers; it never exposes verifier source to the model.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from causal_attribution import CausalAttribution  # noqa: E402
from causal_graph import CausalGraph  # noqa: E402
from counterfactual_repair import CounterfactualRepair  # noqa: E402
from llm_client import LLMClient  # noqa: E402
from replay_graph.builder import step_node_id  # noqa: E402
from trace_logger import StepType, TraceLogger  # noqa: E402
from repro_wrappers.diagnose_openrouter import load_key  # noqa: E402
from repro_wrappers.run_skillsbench_causalflow_repair import (  # noqa: E402
    _build_image,
    _ctrf_counts,
    _graph_step_dependencies,
    _expected_final_write_hashes,
    _read_skills,
    _replay_fidelity_report,
    _run_branch,
)
from repro_wrappers.skillsbench_deployed_skills import (  # noqa: E402
    resolve_deployed_skills,
)
from skillsbench_replay.atif import load_run, materialize_replay_command  # noqa: E402
from skillsbench_replay.graph import (  # noqa: E402
    SkillsBenchGraphBuilder,
    infer_task_workspace,
    infer_verifier_reads,
)


def _use_existing_image(image: str) -> dict[str, Any]:
    """Validate and record an explicitly prebuilt task image."""

    completed = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", image],
        capture_output=True,
        text=True,
        check=False,
    )
    image_id = completed.stdout.strip()
    if completed.returncode != 0 or not image_id:
        detail = completed.stderr.strip() or "image was not found"
        raise SystemExit(f"cannot use existing image {image!r}: {detail}")
    return {
        "image": image,
        "image_id": image_id,
        "seconds": 0.0,
        "skipped": True,
        "reason": "explicitly validated prebuilt image",
    }


def _execution_coverage(parsed) -> tuple[list[Any], dict[str, Any]]:
    """Separate executed shell commands from rejected empty tool calls.

    ACP can record a failed ``run_shell`` invocation whose arguments did not
    contain a command.  Such an event never reached the shell and cannot have
    changed container state.  It remains part of the audited trajectory, but
    strict command replay and CRS operate only on calls that actually supplied
    an executable command.  A non-empty command still requires the lossless
    result marker and is never silently dropped.
    """

    execute_events = [
        event for event in parsed.events if event.kind == "execute"
    ]
    command_events = [event for event in execute_events if event.command]
    non_executable = [
        {
            "step_id": event.step_id,
            "tool_call_id": event.tool_call_id,
            "title": event.title,
            "status": event.status,
            "recorded_output": event.output,
        }
        for event in execute_events
        if not event.command
    ]
    return command_events, {
        "execute_tool_events": len(execute_events),
        "executable_command_events": len(command_events),
        "non_executable_execute_events": non_executable,
    }


def _execution_run(parsed):
    """Keep recorded provenance intact while aligning shell-only replay checks."""
    execution_run = copy.copy(parsed)
    execution_run.events, _ = _execution_coverage(parsed)
    return execution_run


def _direct_producer_steps(graph, target_node: str) -> list[int]:
    resources = {edge.source for edge in graph.edges if edge.target == target_node}
    producers: set[int] = set()
    for edge in graph.edges:
        if edge.target not in resources or not edge.source.startswith("step:"):
            continue
        node = graph.nodes.get(edge.source)
        if node is not None and node.step_id is not None:
            producers.add(node.step_id)
    return sorted(producers)


def _final_state_support_steps(parsed, graph) -> list[int]:
    """Return the minimal recorded producers needed to preserve baseline state.

    A counterfactual branch starts from the pristine task image. Replaying only
    the target's ancestors and descendants can therefore erase independent
    successful edits from the baseline. That is not a one-step intervention:
    the verifier sees several changes at once. Preserve the final producer for
    every observed agent-written path, together with each producer's graph
    prerequisites, so unrelated baseline work remains present in every branch.
    """

    final_writer_by_path: dict[str, int] = {}
    for event in parsed.events:
        for path in event.inferred_deletes:
            final_writer_by_path.pop(path, None)
        for path in event.observed_writes:
            final_writer_by_path[path] = event.step_id

    support: set[int] = set()
    for writer_step in final_writer_by_path.values():
        prerequisites, _ = _graph_step_dependencies(graph, writer_step)
        support.update(prerequisites)
        support.add(writer_step)
    return sorted(support)


def _counterfactual_replay_steps(
    parsed,
    graph,
    *,
    target_step: int,
    final_state_support_steps: list[int],
    replay_mode: str,
) -> tuple[set[int], list[int], list[int], str]:
    """Select recorded commands for one counterfactual branch.

    ``full-trace`` restores the exact prefix in a pristine container, replaces
    one target command, and then executes the complete recorded suffix.  This
    is the faithful deterministic analogue of ``run_remaining_steps`` when a
    container snapshot before every trace step is unavailable.

    ``graph-slice`` is the lower-cost selective mode.  It retains graph
    prerequisites, graph descendants, and final baseline file producers.
    """

    prerequisite_ids, downstream_ids = _graph_step_dependencies(
        graph, target_step
    )
    if replay_mode == "full-trace":
        selected_ids = {
            event.step_id for event in parsed.events
            if event.kind == "execute" and event.command
        }
        label = "full_trace_exact_prefix_and_full_suffix"
    elif replay_mode == "graph-slice":
        selected_ids = set(
            (
                *prerequisite_ids,
                *downstream_ids,
                *final_state_support_steps,
                target_step,
            )
        )
        label = "graph_slice_with_final_baseline_state"
    else:
        raise ValueError(f"unsupported counterfactual replay mode: {replay_mode}")
    return selected_ids, prerequisite_ids, downstream_ids, label


def _counterfactual_outcome_succeeds(
    reward: float | None,
    *,
    baseline_reward: float | None,
    outcome_mode: str,
) -> bool:
    """Map an official reward to the binary outcome expected by original CRS.

    The default preserves the paper implementation's full-success gate.  The
    reward-improvement mode is an explicitly labelled SkillsBench experiment
    for tasks whose official verifier exposes useful partial credit.
    """

    if reward is None:
        return False
    if outcome_mode == "full-success":
        return reward == 1.0
    if outcome_mode == "reward-improvement":
        return baseline_reward is not None and reward > baseline_reward + 1e-12
    raise ValueError(f"unsupported causal outcome mode: {outcome_mode}")


def build_causalflow_trace(parsed, graph, task_context: str) -> tuple[TraceLogger, dict[int, Any]]:
    trace = TraceLogger(problem_statement=task_context, gold_answer=None)
    command_events, _ = _execution_coverage(parsed)
    event_to_trace: dict[int, int] = {}
    trace_to_event: dict[int, Any] = {}
    for event in command_events:
        producer_events = _direct_producer_steps(graph, step_node_id(event.step_id))
        dependencies = [
            event_to_trace[event_id]
            for event_id in producer_events
            if event_id in event_to_trace
        ]
        trace_step_id = trace.log_tool_call(
            "run_shell",
            {"command": event.command},
            dependencies=dependencies,
            resource_reads=list(
                dict.fromkeys((*event.observed_reads, *event.inferred_reads))
            ),
        )
        step = trace.get_step(trace_step_id)
        assert step is not None
        step.resource_writes = list(
            dict.fromkeys((*event.observed_writes, *event.inferred_writes))
        )
        step.state_snapshot = {
            "skillsbench_event_step_id": event.step_id,
            "tool_call_id": event.tool_call_id,
            "argument_source": event.argument_source,
            "recorded_output_tail": (event.output or "")[-4_000:],
        }
        event_to_trace[event.step_id] = trace_step_id
        trace_to_event[trace_step_id] = event

    verifier_producers = _direct_producer_steps(graph, "verifier:skillsbench")
    final_dependencies = [
        event_to_trace[event_id]
        for event_id in verifier_producers
        if event_id in event_to_trace
    ]
    if not final_dependencies and command_events:
        final_dependencies = [event_to_trace[command_events[-1].step_id]]
    trace.log_final_answer(
        f"official_reward={parsed.reward}",
        dependencies=final_dependencies,
    )
    trace.success = parsed.reward == 1.0
    trace.final_answer = f"official_reward={parsed.reward}"
    return trace, trace_to_event


class SkillsBenchDockerReexecutor:
    def __init__(
        self,
        *,
        original_trace: TraceLogger,
        trace_to_event: dict[int, Any],
        parsed,
        graph,
        image: str,
        task_dir: Path,
        skills_root: Path,
        timeout: int,
        replay_mode: str,
        outcome_mode: str,
    ) -> None:
        self.original_trace = original_trace
        self.trace_to_event = trace_to_event
        self.parsed = parsed
        self.graph = graph
        self.image = image
        self.task_dir = task_dir
        self.timeout = timeout
        self.replay_mode = replay_mode
        self.outcome_mode = outcome_mode
        self.skills_root = skills_root
        self.workspace = infer_task_workspace(task_dir)
        self.phase = "unknown"
        self.evaluations: list[dict[str, Any]] = []
        self.full_command_count = len(_execution_coverage(parsed)[0])
        self.final_state_support_steps = _final_state_support_steps(parsed, graph)

    def _failed_trace(self, history, reason: str) -> TraceLogger:
        trace = TraceLogger(problem_statement=self.original_trace.problem_statement)
        trace.steps = [copy.deepcopy(step) for step in history]
        trace.current_step_id = len(trace.steps)
        trace.log_final_answer(f"reexecution_error={reason}")
        trace.success = False
        trace.final_answer = f"reexecution_error={reason}"
        return trace

    def run_remaining_steps(self, history) -> TraceLogger:
        target_step = history[-1]
        event = self.trace_to_event.get(target_step.step_id)
        tool_args = target_step.tool_args if isinstance(target_step.tool_args, dict) else {}
        replacement = tool_args.get("command")
        if event is None or target_step.tool_name != "run_shell" or not isinstance(
            replacement, str
        ) or not replacement.strip():
            reason = "intervention is outside the recorded run_shell action space"
            self.evaluations.append(
                {
                    "phase": self.phase,
                    "trace_step_id": target_step.step_id,
                    "error": reason,
                    "reward": None,
                }
            )
            return self._failed_trace(history, reason)

        (
            selected_ids,
            prerequisite_ids,
            downstream_ids,
            replay_mode_label,
        ) = _counterfactual_replay_steps(
            self.parsed,
            self.graph,
            target_step=event.step_id,
            final_state_support_steps=self.final_state_support_steps,
            replay_mode=self.replay_mode,
        )
        commands: list[str] = []
        selected_event_steps: list[int] = []
        command_timeouts: list[float] = []
        for item in self.parsed.events:
            if item.kind != "execute" or item.step_id not in selected_ids or not item.command:
                continue
            selected_event_steps.append(item.step_id)
            command_timeouts.append(item.replay_timeout or min(self.timeout, 120))
            commands.append(
                replacement.strip()
                if item.step_id == event.step_id
                else materialize_replay_command(item)
            )
        started = time.perf_counter()
        evaluation = _run_branch(
            image=self.image,
            task_dir=self.task_dir,
            skills_root=self.skills_root,
            workspace=self.workspace,
            commands=commands,
            timeout=self.timeout,
            command_timeouts=command_timeouts,
        )
        elapsed = time.perf_counter() - started
        record = {
            "phase": self.phase,
            "trace_step_id": target_step.step_id,
            "skillsbench_event_step_id": event.step_id,
            "replacement_command_sha256": hashlib.sha256(
                replacement.encode("utf-8")
            ).hexdigest(),
            "prerequisite_event_steps": prerequisite_ids,
            "downstream_event_steps": downstream_ids,
            "baseline_support_event_steps": self.final_state_support_steps,
            "selected_event_steps": selected_event_steps,
            "replay_mode": replay_mode_label,
            "commands_replayed": len(commands),
            "full_trace_commands": self.full_command_count,
            "replay_ratio": (
                len(commands) / self.full_command_count
                if self.full_command_count
                else None
            ),
            "reward": evaluation.get("reward"),
            "ctrf": evaluation.get("ctrf"),
            "seconds": elapsed,
            "return_code": evaluation.get("return_code"),
            "command_return_codes": [
                item.get("return_code")
                for item in evaluation.get("command_executions") or []
            ],
            "log_tail": evaluation.get("log_tail"),
        }
        self.evaluations.append(record)
        print(json.dumps({"event": "counterfactual_replay_complete", "phase": self.phase,
                          "step_id": target_step.step_id, "reward": evaluation.get("reward"),
                          "seconds": elapsed}), flush=True)

        trace = TraceLogger(problem_statement=self.original_trace.problem_statement)
        trace.steps = [copy.deepcopy(step) for step in history]
        trace.current_step_id = len(trace.steps)
        trace.log_final_answer(
            f"official_reward={evaluation.get('reward')}",
            dependencies=[target_step.step_id],
        )
        trace.success = _counterfactual_outcome_succeeds(
            evaluation.get("reward"),
            baseline_reward=self.parsed.reward,
            outcome_mode=self.outcome_mode,
        )
        trace.final_answer = f"official_reward={evaluation.get('reward')}"
        return trace


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--task-dir", type=Path, required=True)
    parser.add_argument(
        "--skills-dir",
        type=Path,
        help="exact deployed Skill bundle; defaults to run-dir/inputs/skills",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get(
            "CAUSALFLOW_MODEL", "anthropic/claude-opus-4.7"
        ),
    )
    parser.add_argument("--crs-interventions", type=int, default=1)
    parser.add_argument("--repair-proposals", type=int, default=3)
    parser.add_argument(
        "--llm-max-tokens",
        type=int,
        default=2_048,
        help=(
            "Maximum completion tokens for CRS/repair structured responses. "
            "The cap avoids provider credit rejection and does not change the "
            "CausalFlow intervention or replay algorithm."
        ),
    )
    parser.add_argument(
        "--counterfactual-replay-mode",
        choices=("graph-slice", "full-trace"),
        default="full-trace",
        help=(
            "full-trace (default) restores the exact prefix and executes the "
            "complete suffix; graph-slice is an explicit lower-cost mode"
        ),
    )
    parser.add_argument(
        "--causal-outcome-mode",
        choices=("full-success", "reward-improvement"),
        default="full-success",
        help=(
            "full-success preserves original binary CRS; reward-improvement "
            "is an experimental SkillsBench partial-credit gate"
        ),
    )
    parser.add_argument(
        "--completion-aware-interventions",
        action="store_true",
        help=(
            "diagnostic extension: allow a target command to complete missing "
            "deliverables when the recorded trajectory ended prematurely"
        ),
    )
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument(
        "--strict-replay-only",
        action="store_true",
        help=(
            "stop after the strict baseline replay and identity/hash audit; "
            "this mode makes no model calls and is intended only to revalidate "
            "an existing full CRS run"
        ),
    )
    parser.add_argument(
        "--verified-fidelity-migration",
        type=Path,
        help=(
            "JSON evidence for legacy size-only artifacts. Each artifact must "
            "contain the recorded legacy digest and at least two identical "
            "fresh full-content replay digests. The evidence is retained in "
            "the result and never inferred from the current branch alone."
        ),
    )
    parser.add_argument(
        "--shared-executor-replay-audit",
        type=Path,
        help=(
            "official-equivalent double-replay evidence for a public shared-"
            "executor rollout whose original workspace/resource hashes were "
            "not exported"
        ),
    )
    image_group = parser.add_mutually_exclusive_group()
    image_group.add_argument("--image", help="image tag to build from task-dir")
    image_group.add_argument(
        "--existing-image",
        help=(
            "use an already built task image after docker image inspect; "
            "the default still rebuilds task-dir"
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    run_dir = args.run_dir.resolve()
    task_dir = args.task_dir.resolve()
    skills_root, skills_source = resolve_deployed_skills(
        run_dir, task_dir, args.skills_dir
    )
    parsed = load_run(run_dir)
    command_events, execution_coverage = _execution_coverage(parsed)
    shared_replay_audit = None
    if args.shared_executor_replay_audit:
        shared_replay_audit = json.loads(
            args.shared_executor_replay_audit.read_text()
        )
        if shared_replay_audit.get("task") != task_dir.name:
            raise SystemExit("shared-executor replay audit task does not match task-dir")
        if Path(shared_replay_audit.get("run_dir", "")).resolve() != run_dir:
            raise SystemExit("shared-executor replay audit run_dir does not match")
        if shared_replay_audit.get("official_equivalent_replay") is not True:
            raise SystemExit("shared-executor replay audit did not pass")
        if shared_replay_audit.get("saved_reward") != parsed.reward:
            raise SystemExit("shared-executor replay audit reward does not match")
        if shared_replay_audit.get("command_count") != len(command_events):
            raise SystemExit("shared-executor replay audit command count does not match")
    exact_argument_sources = {
        "result_marker",
        "llm_trajectory.arguments.command",
        "llm_trajectory.file_editor.create",
        "llm_trajectory.file_editor.str_replace",
    }
    bad_steps = [
        event.step_id
        for event in command_events
        if not event.replayable
        or (
            event.argument_source not in exact_argument_sources
            if shared_replay_audit is not None
            else event.argument_source != "result_marker"
        )
    ]
    if bad_steps:
        raise SystemExit(
            "full CRS requires exact command arguments for every executable "
            "call; legacy runs need result markers and shared-executor runs "
            "need a passing double-replay audit; "
            f"bad steps={bad_steps}"
        )

    verifier_paths = infer_verifier_reads(task_dir / "verifier")
    workspace = infer_task_workspace(task_dir)
    graph = SkillsBenchGraphBuilder().build(
        parsed.events,
        verifier_reads=verifier_paths,
        workspace_root=workspace,
    )
    task_context = (
        (task_dir / "task.md").read_text(errors="replace")[:12_000]
        + "\n\nDEPLOYED SKILLS\n"
        + _read_skills(skills_root)
    )
    trace, trace_to_event = build_causalflow_trace(parsed, graph, task_context)
    if args.existing_image:
        image = args.existing_image
        build = _use_existing_image(image)
    else:
        image = args.image or f"causalflow-skillsbench-{task_dir.name}:full-crs"
        build = _build_image(task_dir, image, args.timeout)

    all_commands = [materialize_replay_command(event) for event in command_events]
    baseline_replay = _run_branch(
        image=image,
        task_dir=task_dir,
        skills_root=skills_root,
        workspace=workspace,
        commands=all_commands,
        timeout=args.timeout,
        command_timeouts=[event.replay_timeout or min(args.timeout, 120)
                          for event in command_events],
    )
    migration_evidence = None
    digest_overrides: dict[str, str] = {}
    if args.verified_fidelity_migration:
        migration_evidence = json.loads(
            args.verified_fidelity_migration.read_text()
        )
        if migration_evidence.get("task") != task_dir.name:
            raise SystemExit("fidelity migration task does not match task-dir")
        recorded_hashes, _ = _expected_final_write_hashes(parsed)
        artifacts = migration_evidence.get("artifacts")
        if not isinstance(artifacts, dict) or not artifacts:
            raise SystemExit("fidelity migration has no artifacts")
        for path, evidence in artifacts.items():
            if not isinstance(evidence, dict):
                raise SystemExit(f"invalid fidelity evidence for {path}")
            legacy = evidence.get("recorded_legacy_digest")
            digests = evidence.get("fresh_full_content_digests")
            if recorded_hashes.get(path) != legacy:
                raise SystemExit(f"legacy fidelity digest mismatch for {path}")
            if (
                not isinstance(digests, list)
                or len(digests) < 2
                or not all(isinstance(item, str) and item for item in digests)
                or len(set(digests)) != 1
            ):
                raise SystemExit(
                    f"fidelity migration for {path} requires two identical digests"
                )
            digest_overrides[path] = digests[0]

    baseline_fidelity = _replay_fidelity_report(
        _execution_run(parsed),
        baseline_replay,
        original_artifact_root=run_dir / "agent",
        expected_digest_overrides=digest_overrides,
    )
    baseline_fidelity["exact_tool_arguments"] = not bad_steps
    baseline_fidelity["shared_executor_official_equivalent_double_replay"] = (
        shared_replay_audit is not None
    )
    baseline_fidelity["original_workspace_hashes_available"] = (
        shared_replay_audit is None
    )
    if shared_replay_audit is not None:
        baseline_fidelity["artifact_hashes_match"] = None
        baseline_fidelity["artifact_hash_comparison"] = (
            "unavailable because the public executor did not export the "
            "original submitted workspace; double-replay manifests matched"
        )
    saved_ctrf = _ctrf_counts(run_dir)
    common_baseline_matches = (
        baseline_replay.get("reward") == parsed.reward
        and (saved_ctrf is None or baseline_replay.get("ctrf") == saved_ctrf)
        and baseline_fidelity["command_count_matches"]
        and baseline_fidelity["return_codes_match"]
        and baseline_fidelity["sandbox_identity_matches"]
        and baseline_fidelity["exact_tool_arguments"]
    )
    baseline_matches = common_baseline_matches and (
        shared_replay_audit is not None
        or (
            baseline_fidelity["lossless_command_markers"]
            and baseline_fidelity["artifact_hashes_match"]
        )
    )
    if not baseline_matches:
        invalid_result = {
            "experiment": "SkillsBench trajectory through original CausalFlow CRS",
            "status": "invalid_baseline_replay",
            "task": task_dir.name,
            "baseline_run": str(run_dir),
            "deployed_skills_dir": str(skills_root),
            "deployed_skills_source": skills_source,
            "baseline_official_reward": parsed.reward,
            "baseline_saved_ctrf": saved_ctrf,
            "baseline_fresh_replay": baseline_replay,
            "baseline_replay_fidelity": baseline_fidelity,
            "verified_fidelity_migration": migration_evidence,
            "shared_executor_replay_audit": shared_replay_audit,
            "strict_baseline_replay_matches": False,
            "build": build,
            "model": args.model,
            "counterfactual_replay_mode": args.counterfactual_replay_mode,
            "causal_outcome_mode": args.causal_outcome_mode,
            "trajectory_execution_coverage": execution_coverage,
            "causal_attribution": {
                "skipped": True,
                "reason": "strict baseline replay failed",
            },
            "counterfactual_repair": {
                "skipped": True,
                "reason": "strict baseline replay failed",
            },
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(invalid_result, ensure_ascii=False, indent=2) + "\n"
        )
        print(f"output={args.output.resolve()}")
        print(
            "baseline replay failed strict fidelity: "
            + json.dumps(baseline_fidelity, ensure_ascii=False)
        )
        return 2

    result: dict[str, Any] = {
        "experiment": (
            "SkillsBench trajectory through completion-aware CausalFlow diagnostic"
            if args.completion_aware_interventions
            else (
                "SkillsBench trajectory through original CausalFlow CRS"
                if args.causal_outcome_mode == "full-success"
                else "SkillsBench trajectory through reward-improvement CRS extension"
            )
        ),
        "counted_as_formal_causalflow_result": not args.completion_aware_interventions,
        "task": task_dir.name,
        "baseline_run": str(run_dir),
        "deployed_skills_dir": str(skills_root),
        "deployed_skills_source": skills_source,
        "baseline_official_reward": parsed.reward,
        "baseline_saved_ctrf": saved_ctrf,
        "baseline_fresh_replay": baseline_replay,
        "baseline_replay_fidelity": baseline_fidelity,
        "verified_fidelity_migration": migration_evidence,
        "shared_executor_replay_audit": shared_replay_audit,
        "replay_evidence_tier": (
            "official_equivalent_double_replay"
            if shared_replay_audit is not None
            else "strict_original_artifact_identity"
        ),
        "strict_baseline_replay_matches": baseline_matches,
        "build": build,
        "model": args.model,
        "llm_max_tokens": args.llm_max_tokens,
        "counterfactual_replay_mode": args.counterfactual_replay_mode,
        "causal_outcome_mode": args.causal_outcome_mode,
        "completion_aware_interventions": args.completion_aware_interventions,
        "trajectory_execution_coverage": execution_coverage,
        "evidence_policy": {
            "shown_to_model": [
                "task.md",
                "deployed skill Markdown",
                "recorded command/dependency context",
                "target command recorded output tail",
            ],
            "withheld_from_model": ["verifier source", "expected answers", "verifier stdout/stderr"],
        },
        "trace": trace.to_dict(),
        "file_graph": graph.to_dict(),
    }

    if args.strict_replay_only:
        result["causal_attribution"] = {
            "skipped": True,
            "reason": "strict replay identity audit only",
        }
        result["counterfactual_repair"] = {
            "skipped": True,
            "reason": "strict replay identity audit only",
        }
        result["summary"] = {
            "causal_steps": 0,
            "best_local_repair_reward": None,
            "local_repair_full_success": None,
            "audit_only": True,
        }
    elif parsed.reward is not None and parsed.reward < 1.0:
        api_key, key_source = load_key()
        llm = LLMClient(
            api_key=api_key,
            model=args.model,
            temperature=0.35,
            max_tokens=args.llm_max_tokens,
        )
        causal_graph = CausalGraph(trace)
        reexecutor = SkillsBenchDockerReexecutor(
            original_trace=trace,
            trace_to_event=trace_to_event,
            parsed=parsed,
            graph=graph,
            image=image,
            task_dir=task_dir,
            skills_root=skills_root,
            timeout=args.timeout,
            replay_mode=args.counterfactual_replay_mode,
            outcome_mode=args.causal_outcome_mode,
        )
        attribution = CausalAttribution(
            trace=trace,
            causal_graph=causal_graph,
            llm_client=llm,
            re_executor=reexecutor,
            completion_aware_interventions=args.completion_aware_interventions,
        )
        attribution_started = time.perf_counter()
        reexecutor.phase = "crs_attribution"
        crs_scores = attribution.compute_causal_responsibility(
            execution_context={},
            intervene_step_types={StepType.TOOL_CALL},
            num_interventions=args.crs_interventions,
        )
        attribution_seconds = time.perf_counter() - attribution_started
        causal_steps = attribution.get_causal_steps()

        repair = CounterfactualRepair(
            trace=trace,
            causal_attribution=attribution,
            llm_client=llm,
            reexecutor=reexecutor,
            execution_context={},
            num_proposals=args.repair_proposals,
            compute_semantic_minimality=False,
            use_gold_in_prompts=False,
        )
        repair_started = time.perf_counter()
        reexecutor.phase = "counterfactual_repair"
        repairs = repair.generate_repairs(causal_steps)
        repair_seconds = time.perf_counter() - repair_started
        result["causal_attribution"] = {
            "crs_scores": crs_scores,
            "causal_steps": causal_steps,
            "intervention_results": attribution.intervention_results,
            "seconds": attribution_seconds,
        }
        result["counterfactual_repair"] = {
            str(step_id): [candidate.to_dict() for candidate in candidates]
            for step_id, candidates in repairs.items()
        }
        result["repair_seconds"] = repair_seconds
        result["reexecution_evaluations"] = reexecutor.evaluations
        result["model_usage"] = {
            "key_source": key_source,
            "totals": llm.usage_totals,
            "calls": llm.usage_calls,
            "structured_attempts": llm.structured_attempts,
        }
        repair_evaluations = [
            item
            for item in reexecutor.evaluations
            if item.get("phase") == "counterfactual_repair"
        ]
        result["summary"] = {
            "causal_steps": len(causal_steps),
            "crs_interventions_evaluated": sum(
                len(item.get("attempts") or [])
                for item in attribution.intervention_results.values()
            ),
            "repair_candidates_evaluated": len(repair_evaluations),
            "best_local_repair_reward": max(
                (item.get("reward") for item in repair_evaluations if item.get("reward") is not None),
                default=None,
            ),
            "best_attribution_reward": max(
                (
                    item.get("reward")
                    for item in reexecutor.evaluations
                    if item.get("phase") == "crs_attribution"
                    and item.get("reward") is not None
                ),
                default=None,
            ),
            "local_repair_full_success": any(
                item.get("reward") == 1.0 for item in repair_evaluations
            ),
            "mean_replay_ratio": (
                sum(item["replay_ratio"] for item in reexecutor.evaluations if item.get("replay_ratio") is not None)
                / sum(item.get("replay_ratio") is not None for item in reexecutor.evaluations)
                if any(item.get("replay_ratio") is not None for item in reexecutor.evaluations)
                else None
            ),
        }
    else:
        result["causal_attribution"] = {"skipped": True, "reason": "baseline passed"}
        result["counterfactual_repair"] = {"skipped": True, "reason": "baseline passed"}
        result["summary"] = {
            "causal_steps": 0,
            "best_local_repair_reward": None,
            "local_repair_full_success": None,
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"output={args.output.resolve()}")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
