from __future__ import annotations

from collections.abc import Sequence

from skillrevise.method.authoring import SkillAuthor
from skillrevise.method.diagnosis import Diagnoser
from skillrevise.core.metrics import trace_outcome_score
from skillrevise.core.models import (
    DiagnosisEvidence,
    DiagnosisReport,
    ExecutionTrace,
    HarnessIteration,
    HarnessResult,
    PairedEvaluation,
    RepairPrinciple,
    Skill,
    TaskSpec,
)
from skillrevise.method.principles import PrincipleAbsorber
from skillrevise.method.revision import RevisionEngine
from skillrevise.core.runner import PairedRunner


class HarnessLoop:
    def __init__(
        self,
        *,
        author: SkillAuthor,
        runner: PairedRunner,
        diagnoser: Diagnoser,
        reviser: RevisionEngine,
        max_revisions: int = 1,
        principle_absorber: PrincipleAbsorber | None = None,
        continue_after_non_improving_revision: bool = False,
        require_diagnosis_for_revision: bool = True,
        paper_protocol: bool = False,
    ) -> None:
        self.author = author
        self.runner = runner
        self.diagnoser = diagnoser
        self.reviser = reviser
        self.max_revisions = max_revisions
        self.principle_absorber = principle_absorber
        self.absorbed_principles: list[RepairPrinciple] = []
        self.continue_after_non_improving_revision = continue_after_non_improving_revision
        self.require_diagnosis_for_revision = require_diagnosis_for_revision
        self.paper_protocol = paper_protocol

    def run_task(self, task: TaskSpec, *, heldout_tasks: Sequence[TaskSpec] | None = None) -> HarnessResult:
        return self.run_task_from_initial_skill(
            task,
            self.author.author(task),
            heldout_tasks=heldout_tasks,
        )

    def run_task_from_initial_skill(
        self,
        task: TaskSpec,
        initial_skill: Skill,
        *,
        heldout_tasks: Sequence[TaskSpec] | None = None,
    ) -> HarnessResult:
        """Run the normal v0→vN loop from a caller-supplied frozen v0.

        Bundle-level orchestration uses this entry point to repair one
        official Skill at a time.  The inner diagnosis/revision policy is
        unchanged; only v0 provenance differs from paper-style LLM authoring.
        """
        current_eval = self.runner.evaluate(task, initial_skill, transfer_tasks=heldout_tasks)
        return self.run_task_from_initial_evaluation(
            task,
            initial_skill,
            current_eval,
            heldout_tasks=heldout_tasks,
        )

    def run_task_from_initial_evaluation(
        self,
        task: TaskSpec,
        initial_skill: Skill,
        initial_evaluation: PairedEvaluation,
        *,
        heldout_tasks: Sequence[TaskSpec] | None = None,
    ) -> HarnessResult:
        """Continue revision from a frozen, already-evaluated v0 trace."""
        iterations: list[HarnessIteration] = []

        current_skill = initial_skill
        current_eval = initial_evaluation
        best_skill = current_skill
        best_eval = current_eval

        for iteration_index in range(self.max_revisions + 1):
            if not self._is_valid_for_revision(current_eval):
                iterations.append(
                    HarnessIteration(
                        iteration_index=iteration_index,
                        skill=current_skill,
                        evaluation=current_eval,
                        diagnosis=self._infrastructure_diagnosis(current_eval),
                        revision=None,
                    )
                )
                break

            # Paper protocol: v0/v1/v2/v3 is a failure-conditioned chain.
            # Once the verifier accepts a candidate, do not diagnose it and do
            # not produce another revision.  No Skill belongs to a separate
            # baseline condition and is never consulted here.
            if self.paper_protocol and current_eval.with_skill.success:
                iterations.append(
                    HarnessIteration(
                        iteration_index=iteration_index,
                        skill=current_skill,
                        evaluation=current_eval,
                        diagnosis=self._passing_diagnosis(),
                        revision=None,
                    )
                )
                break

            diagnosis = self.diagnoser.diagnose(task, current_skill, current_eval)
            revision = None

            if iteration_index < self.max_revisions and self._should_revise(current_eval, diagnosis):
                revision = self.reviser.revise(task, current_skill, diagnosis)
                # Bundle-level execution carries a small amount of immutable
                # branch transport state in Skill metadata.  Do *not* merge
                # the entire parent metadata dict here: an input Skill loaded
                # from a frozen bundle has ``raw_markdown`` set, and
                # ``Skill.as_markdown()`` deliberately gives that field
                # precedence over structured fields.  Carrying it into a
                # structured LLM revision therefore makes a real revision
                # serialize as its unchanged parent and falsely appear to be
                # a no-op.
                #
                # These are the only metadata values required later to place
                # a revised Skill back into its original bundle.  A revision
                # that itself is raw keeps its own raw_markdown untouched.
                branch_transport = {
                    key: current_skill.metadata[key]
                    for key in ("bundle_target_relpath", "bundle_overrides")
                    if key in current_skill.metadata
                }
                revision.revised_skill.metadata = (
                    branch_transport | dict(revision.revised_skill.metadata)
                )

            iterations.append(
                HarnessIteration(
                    iteration_index=iteration_index,
                    skill=current_skill,
                    evaluation=current_eval,
                    diagnosis=diagnosis,
                    revision=revision,
                )
            )

            if revision is None:
                break

            if _same_skill_text(current_skill, revision.revised_skill):
                revision.metadata["no_op_revision"] = True
                revision.metadata["no_op_reason"] = (
                    "The revision produced byte-identical Skill Markdown; no rollout was run."
                )
                break

            candidate_eval = self.runner.evaluate(task, revision.revised_skill, transfer_tasks=heldout_tasks)
            if not self._is_valid_for_revision(candidate_eval):
                # The candidate is retained as evidence, but it cannot be
                # diagnosed, selected, or used to produce a further version.
                # PairedRunner has already retried this exact Skill according
                # to its configured evaluation-attempt budget.
                iterations.append(
                    HarnessIteration(
                        iteration_index=iteration_index + 1,
                        skill=revision.revised_skill,
                        evaluation=candidate_eval,
                        diagnosis=self._infrastructure_diagnosis(candidate_eval),
                        revision=None,
                    )
                )
                break
            if self._is_better(candidate_eval, best_eval):
                best_skill = revision.revised_skill
                best_eval = candidate_eval

            if self._is_better(candidate_eval, current_eval):
                current_skill = revision.revised_skill
                current_eval = candidate_eval
            elif (
                not self.paper_protocol
                and self.continue_after_non_improving_revision
                and iteration_index + 1 < self.max_revisions
            ):
                current_skill = revision.revised_skill
                current_eval = candidate_eval
            else:
                iterations.append(
                    HarnessIteration(
                        iteration_index=iteration_index + 1,
                        skill=revision.revised_skill,
                        evaluation=candidate_eval,
                        diagnosis=self.diagnoser.diagnose(task, revision.revised_skill, candidate_eval),
                        revision=None,
                    )
                )
                break

        result = HarnessResult(
            task=task,
            initial_skill=initial_skill,
            iterations=iterations,
            selected_skill=best_skill,
            selected_evaluation=best_eval,
        )
        self._absorb_episode_if_enabled(result)
        return result

    def _is_better(self, candidate: PairedEvaluation, incumbent: PairedEvaluation) -> bool:
        candidate_is_valid = self._is_valid_for_revision(candidate)
        incumbent_is_valid = self._is_valid_for_revision(incumbent)
        if candidate_is_valid != incumbent_is_valid:
            return candidate_is_valid
        if not candidate_is_valid:
            return False
        if self.paper_protocol and candidate.with_skill.success != incumbent.with_skill.success:
            return candidate.with_skill.success and not incumbent.with_skill.success
        if candidate.utility.overall_score != incumbent.utility.overall_score:
            return candidate.utility.overall_score > incumbent.utility.overall_score
        if candidate.with_skill.success != incumbent.with_skill.success:
            return candidate.with_skill.success and not incumbent.with_skill.success
        candidate_has_valid_trace = self._has_selectable_with_skill_trace(candidate)
        incumbent_has_valid_trace = self._has_selectable_with_skill_trace(incumbent)
        if candidate_has_valid_trace != incumbent_has_valid_trace:
            return candidate_has_valid_trace
        return self._efficiency_key(candidate.with_skill) < self._efficiency_key(incumbent.with_skill)

    def _efficiency_key(self, trace: ExecutionTrace) -> tuple[int, int, int, int]:
        token_count = self._positive_int_or_none(trace.tokens)
        tool_calls = self._nonnegative_int(trace.tool_calls)
        steps = self._nonnegative_int(trace.steps)
        if token_count is not None:
            return (0, token_count, tool_calls, steps)
        return (1, tool_calls, steps, 0)

    def _positive_int_or_none(self, value: int | float | None) -> int | None:
        if isinstance(value, bool) or value is None:
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    def _nonnegative_int(self, value: int | float | None) -> int:
        if isinstance(value, bool) or value is None:
            return 0
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return 0

    def _has_selectable_with_skill_trace(self, evaluation: PairedEvaluation) -> bool:
        trace = evaluation.with_skill
        if PairedRunner.is_infrastructure_failure(trace):
            return False
        if trace_outcome_score(trace) is None:
            return False
        if not trace.events and trace.tool_calls == 0:
            return False
        return True

    def _trace_timed_out(self, trace: ExecutionTrace) -> bool:
        return bool(trace.metadata.get("timed_out")) or trace.status == "timeout"

    def _is_valid_for_revision(self, evaluation: PairedEvaluation) -> bool:
        trace = evaluation.with_skill
        if PairedRunner.is_infrastructure_failure(trace):
            return False
        if not any("no valid benchmark reward" in note for note in evaluation.utility.notes):
            return True
        return bool(trace.events) or trace.tool_calls > 0 or trace.steps > 0

    def _should_revise(self, evaluation: PairedEvaluation, diagnosis) -> bool:
        if self.require_diagnosis_for_revision and not diagnosis.labels:
            return False
        if not self._is_valid_for_revision(evaluation):
            return False
        reward = evaluation.with_skill.metadata.get("reward")
        if self.paper_protocol and evaluation.with_skill.success:
            return False
        if evaluation.with_skill.success and isinstance(reward, (int, float)) and reward >= 1.0:
            return False
        return bool(diagnosis.labels) or not self.require_diagnosis_for_revision

    @staticmethod
    def _passing_diagnosis() -> DiagnosisReport:
        return DiagnosisReport(
            labels=[],
            evidence=[],
            causal_judgment=(
                "Verifier accepted this Skill version; the paper protocol stops before diagnosis or revision."
            ),
            rewrite_targets=[],
            summary="Verifier passed: no SkillRevise diagnosis or further revision was run.",
        )

    def _infrastructure_diagnosis(self, evaluation: PairedEvaluation) -> DiagnosisReport:
        trace = evaluation.with_skill
        reason = str(
            trace.metadata.get("harness_error")
            or trace.metadata.get("executor_error")
            or trace.outcome_summary
            or "The execution trace is not valid for causal Skill diagnosis."
        )
        return DiagnosisReport(
            labels=[],
            evidence=[
                DiagnosisEvidence(
                    source="infrastructure",
                    snippet=reason,
                    reason=(
                        "This run is not a task failure. The same Skill was retried according to the "
                        "evaluation retry policy and must not produce a new revision version."
                    ),
                )
            ],
            causal_judgment="No Skill-level causal judgment is permitted because execution infrastructure failed.",
            rewrite_targets=[],
            summary="Infrastructure failure: do not revise or select this Skill version.",
        )

    def _absorb_episode_if_enabled(self, result: HarnessResult) -> None:
        if self.principle_absorber is None:
            return
        absorbed = self.principle_absorber.absorb_episode(result)
        if absorbed is not None:
            self.absorbed_principles.append(absorbed)


def _same_skill_text(left: Skill, right: Skill) -> bool:
    return left.as_markdown().replace("\r\n", "\n").strip() == right.as_markdown().replace("\r\n", "\n").strip()
