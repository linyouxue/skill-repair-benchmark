"""Structure-preserving orchestration for repairing an official Skill bundle.

The original :class:`HarnessLoop` remains a single-Skill method.  This wrapper
selects candidate files, invokes that unchanged inner loop one file at a time,
and validates every branch as a complete immutable bundle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from skillrevise.benchmarks.unified_executor_adapter import SkillBundleMaterializer, UnifiedBenchmarkAdapter
from skillrevise.core.loop import HarnessLoop
from skillrevise.core.metrics import trace_outcome_score
from skillrevise.core.models import ExecutionTrace, HarnessResult, Skill, TaskSpec
from skillrevise.method.bundle_selection import BundleTargetSelection, LLMBundleSkillSelector


@dataclass
class BundleRepairEpisode:
    target_skill: str
    accepted: bool
    accepted_revision: bool
    decision: str
    score_before: float | None
    score_after: float | None
    result: HarnessResult


@dataclass
class BundleRepairResult:
    task: TaskSpec
    initial_trace: ExecutionTrace
    selection: BundleTargetSelection | None = None
    episodes: list[BundleRepairEpisode] = field(default_factory=list)
    selected_overrides: dict[str, str] = field(default_factory=dict)
    selected_trace: ExecutionTrace | None = None


class BundleRepairLoop:
    """Run candidate Skill repairs sequentially without mutating task sources."""

    def __init__(
        self,
        *,
        loop: HarnessLoop,
        adapter: UnifiedBenchmarkAdapter,
        materializer: SkillBundleMaterializer,
        selector: LLMBundleSkillSelector,
        accept_non_degrading: bool = False,
        initial_evaluation_attempts: int = 3,
        initial_traces: dict[str, ExecutionTrace] | None = None,
    ) -> None:
        self.loop = loop
        self.adapter = adapter
        self.materializer = materializer
        self.selector = selector
        self.accept_non_degrading = accept_non_degrading
        self.initial_evaluation_attempts = max(1, initial_evaluation_attempts)
        self.initial_traces = dict(initial_traces or {})

    def run_task(self, task: TaskSpec) -> BundleRepairResult:
        # The official condition is the gate.  A passed bundle is never
        # exposed to target selection or revision.
        initial_trace = self._initial_trace(task)
        result = BundleRepairResult(task=task, initial_trace=initial_trace, selected_trace=initial_trace)
        if initial_trace.success or _score(initial_trace) is None:
            return result

        paths = self.materializer.skill_paths(task.task_id)
        result.selection = self.selector.select(
            task,
            initial_trace,
            bundle_root=self.materializer.official_bundle_path(task.task_id),
            skill_paths=paths,
        )

        overrides: dict[str, str] = {}
        best_trace = initial_trace
        best_score = _score(initial_trace)
        for ordinal, target in enumerate(result.selection.targets, start=1):
            target_task = self.materializer.with_skill_context(task, target, overrides=overrides)
            initial_version = (
                f"bundle-{ordinal}-published-original"
                if task.task_id in self.initial_traces
                else f"bundle-{ordinal}-v0"
            )
            initial_skill = _skill_from_context(target_task, version=initial_version)
            initial_evaluation = self.loop.runner.evaluation_from_existing_with_skill_trace(
                target_task,
                initial_skill,
                best_trace,
            )
            episode_result = self.loop.run_task_from_initial_evaluation(
                target_task,
                initial_skill,
                initial_evaluation,
            )
            candidate_skill, candidate_trace, is_revision = _candidate_for_bundle_branch(
                episode_result,
                initial_version=initial_version,
                allow_equal=self.accept_non_degrading,
            )
            candidate_score = _score(candidate_trace)
            if not is_revision:
                # A method-skill v0 is byte-identical to the failed Original
                # bundle. A different outcome here is rollout instability or
                # condition drift, never a SkillRevise repair.
                accepted = False
                decision = "rejected_unmodified_v0"
                candidate_trace.metadata["bundle_baseline_inconsistent"] = True
            else:
                accepted = _accept(
                    candidate_trace,
                    candidate_score,
                    best_trace,
                    best_score,
                    allow_equal=self.accept_non_degrading,
                )
                decision = "accepted_revision" if accepted else "rejected_revision_not_better"
            result.episodes.append(
                BundleRepairEpisode(
                    target_skill=target,
                    accepted=accepted,
                    accepted_revision=is_revision and accepted,
                    decision=decision,
                    score_before=best_score,
                    score_after=candidate_score,
                    result=episode_result,
                )
            )
            if accepted:
                overrides[target] = candidate_skill.as_markdown().replace("\r\n", "\n")
                best_trace = candidate_trace
                best_score = candidate_score
                # The paper gate applies after every validated complete-bundle
                # rollout: never continue modifying a passing bundle.
                if best_trace.success:
                    break

        result.selected_overrides = overrides
        result.selected_trace = best_trace
        return result

    def _initial_trace(self, task: TaskSpec) -> ExecutionTrace:
        """Use a frozen published rollout when supplied; otherwise run v0."""
        trace = self.initial_traces.get(task.task_id)
        if trace is None:
            return self._run_initial_with_retries(task)
        if trace.task_id != task.task_id:
            raise ValueError(f"Frozen trace task mismatch: {trace.task_id!r} != {task.task_id!r}")
        trace.metadata = dict(trace.metadata)
        trace.metadata["bundle_initial_trace_source"] = "published_representative"
        trace.metadata["bundle_initial_original_skill_replay_skipped"] = True
        return trace

    def _run_initial_with_retries(self, task: TaskSpec) -> ExecutionTrace:
        """Retry only unusable Original-bundle rollouts before diagnosis.

        A valid verifier failure is a repair signal and is deliberately not
        retried. ACP, Docker, provider and verifier timeouts have no reward,
        so they must never be converted into empty target selections.
        """

        prior_attempts: list[dict[str, object]] = []
        for attempt in range(1, self.initial_evaluation_attempts + 1):
            trace = self.adapter.run_original_skill(task)
            trace.metadata["bundle_initial_evaluation_attempt"] = attempt
            trace.metadata["bundle_initial_evaluation_max_attempts"] = self.initial_evaluation_attempts
            if _score(trace) is not None:
                if prior_attempts:
                    trace.metadata["bundle_initial_retry_recovered"] = True
                    trace.metadata["bundle_initial_previous_attempts"] = prior_attempts
                return trace
            prior_attempts.append(
                {
                    "attempt": attempt,
                    "status": trace.status,
                    "outcome_summary": trace.outcome_summary,
                }
            )
        trace.metadata["bundle_initial_retry_exhausted"] = True
        trace.metadata["bundle_initial_previous_attempts"] = prior_attempts[:-1]
        return trace


def _skill_from_context(task: TaskSpec, *, version: str) -> Skill:
    markdown = task.context.get("original_skill_markdown")
    relpath = task.context.get("original_skill_relpath")
    if not isinstance(markdown, str) or not isinstance(relpath, str):
        raise ValueError("Bundle target task is missing original Skill context.")
    metadata = {
        "raw_markdown": markdown,
        "bundle_target_relpath": relpath,
        "bundle_overrides": dict(task.metadata.get("bundle_overrides", {})),
    }
    return Skill(
        name=Path(relpath).parent.name,
        purpose="Frozen official Skill bundle member.",
        when_to_use="When the task invokes this bundled Skill.",
        procedure=["Preserve the supplied Markdown unless a trace-grounded revision is accepted."],
        constraints=["Other bundle files are frozen for this candidate branch."],
        version=version,
        metadata=metadata,
    )


def _score(trace: ExecutionTrace) -> float | None:
    return trace_outcome_score(trace)


def _candidate_for_bundle_branch(
    result: HarnessResult,
    *,
    initial_version: str,
    allow_equal: bool,
) -> tuple[Skill, ExecutionTrace, bool]:
    """Choose a real revision, never an unchanged v0, for outer selection."""

    selected_skill = result.selected_skill
    selected_trace = result.selected_evaluation.with_skill
    if selected_skill.version != initial_version:
        return selected_skill, selected_trace, True
    if allow_equal:
        # The single-Skill inner loop rightly selects v0 on a score tie.  The
        # bundle extension may retain a tied *revision* to enable a later
        # complementary Skill repair, so recover the last valid edited state.
        for iteration in reversed(result.iterations):
            if iteration.skill.version == initial_version:
                continue
            trace = iteration.evaluation.with_skill
            if _score(trace) is not None:
                return iteration.skill, trace, True
    return selected_skill, selected_trace, False


def _accept(
    candidate: ExecutionTrace,
    candidate_score: float | None,
    incumbent: ExecutionTrace,
    incumbent_score: float | None,
    *,
    allow_equal: bool,
) -> bool:
    if candidate_score is None:
        return False
    if incumbent_score is None:
        return True
    if candidate_score > incumbent_score:
        return True
    # This optional mode supports multi-Skill cases with binary rewards: a
    # partial correct repair may remain at 0 until a second Skill is repaired.
    # It must be reported separately because it can retain a non-improving edit.
    return allow_equal and candidate_score == incumbent_score and candidate.success == incumbent.success
