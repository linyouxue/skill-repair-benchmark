"""Build bounded, graph-aware evidence for repair proposal generation."""

from __future__ import annotations

import json
from typing import Any, Iterable, Optional

from causal_graph import CausalGraph
from trace_logger import Step, StepType, TraceLogger
from utils import summarize_step


DEFAULT_FIELD_LIMIT = 2_000
DEFAULT_LIST_LIMIT = 8
SAFE_EXECUTION_CONTEXT_KEYS = (
    "task_id",
    "entry_point",
    "resolved_entry_point",
    "prompt",
    "tests",
    "question",
    "max_steps",
)


def _bounded(value: Any, max_chars: int = DEFAULT_FIELD_LIMIT) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value if len(value) <= max_chars else value[:max_chars] + "...[truncated]"
    rendered = json.dumps(value, ensure_ascii=False, default=str)
    if len(rendered) <= max_chars:
        return value
    return rendered[:max_chars] + "...[truncated]"


def _step_evidence(step: Optional[Step]) -> Optional[dict[str, Any]]:
    if step is None:
        return None
    return {
        "step_id": step.step_id,
        "step_type": step.step_type.value,
        "summary": _bounded(summarize_step(step)),
        "dependencies": list(step.dependencies),
        "resource_reads": list(step.resource_reads),
        "resource_writes": list(step.resource_writes),
        "state_snapshot": _bounded(step.state_snapshot),
    }


def _failed_downstream_evidence(
    trace: TraceLogger,
    graph: CausalGraph,
    target_step_id: int,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for step_id in sorted(graph.get_descendants(target_step_id)):
        step = trace.get_step(step_id)
        if step is None:
            continue
        is_failure = (
            step.step_type == StepType.FINAL_ANSWER
            or step.tool_call_result is False
            or (
                step.step_type == StepType.TOOL_RESPONSE
                and any(
                    marker in str(step.tool_output or "").lower()
                    for marker in ("error", "failed", "exception", "traceback")
                )
            )
        )
        if is_failure:
            evidence.append(_step_evidence(step) or {})
        if len(evidence) >= DEFAULT_LIST_LIMIT:
            break
    return evidence


def _prior_attempt_evidence(prior_repairs: Iterable[Any]) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    for repair in prior_repairs:
        failure_outputs: list[Any] = []
        repaired_trace = getattr(repair, "repaired_trace", None)
        for step in getattr(repaired_trace, "steps", []) if repaired_trace else []:
            if step.step_type == StepType.TOOL_RESPONSE and step.tool_call_result is False:
                failure_outputs.append(_bounded(step.tool_output, 1_000))
        attempts.append(
            {
                "proposal_idx": getattr(repair, "proposal_idx", None),
                "repaired_text": _bounded(getattr(repair, "repaired_text", None), 1_000),
                "diagnosis": _bounded(getattr(repair, "diagnosis", None), 1_000),
                "expected_output_contract": _bounded(
                    getattr(repair, "expected_output_contract", None), 1_000
                ),
                "behavioral_invariant": _bounded(
                    getattr(repair, "behavioral_invariant", None), 1_000
                ),
                "failure_outputs": failure_outputs[:2],
                "succeeded": bool(getattr(repair, "success_predicted", False)),
            }
        )
        if len(attempts) >= DEFAULT_LIST_LIMIT:
            break
    return attempts


def _acceptance_obligations(execution_context: dict[str, Any]) -> list[str]:
    tests = execution_context.get("tests")
    if not isinstance(tests, str):
        return []
    obligations = [line.strip() for line in tests.splitlines() if line.strip()]
    return [_bounded(line, 1_000) for line in obligations[:DEFAULT_LIST_LIMIT]]


def _expected_output_examples(execution_context: dict[str, Any]) -> list[str]:
    examples: list[str] = []
    for obligation in _acceptance_obligations(execution_context):
        if "==" not in obligation:
            continue
        _, _, expected = obligation.partition("==")
        if expected.strip():
            examples.append(expected.strip())
    return examples


def build_repair_context(
    trace: TraceLogger,
    graph: CausalGraph,
    target_step_id: int,
    *,
    execution_context: Optional[dict[str, Any]] = None,
    causal_step_ids: Optional[Iterable[int]] = None,
    prior_repairs: Optional[Iterable[Any]] = None,
) -> dict[str, Any]:
    """Return local evidence that is useful for repair but bounded in size.

    The pack exposes direct graph neighbors, concrete resource/state evidence,
    task constraints, downstream failures, other attributed causes, and prior
    failed candidates.  It intentionally omits the gold answer so it is safe to
    reuse in no-gold experiments.
    """
    target = trace.get_step(target_step_id)
    parent_ids = sorted(graph.get_immediate_dependencies(target_step_id))
    child_ids = sorted(graph.get_immediate_dependents(target_step_id))
    causal_ids = sorted(set(causal_step_ids or []))
    sibling_ids = [step_id for step_id in causal_ids if step_id != target_step_id]
    safe_context = {
        key: _bounded((execution_context or {}).get(key))
        for key in SAFE_EXECUTION_CONTEXT_KEYS
        if (execution_context or {}).get(key) is not None
    }

    descendants = sorted(graph.get_descendants(target_step_id))
    return {
        "target": _step_evidence(target),
        "direct_inputs": [
            evidence
            for evidence in (_step_evidence(trace.get_step(step_id)) for step_id in parent_ids)
            if evidence is not None
        ],
        "direct_consumers": [
            evidence
            for evidence in (_step_evidence(trace.get_step(step_id)) for step_id in child_ids)
            if evidence is not None
        ],
        "downstream_failure_evidence": _failed_downstream_evidence(
            trace, graph, target_step_id
        ),
        "acceptance_obligations": _acceptance_obligations(execution_context or {}),
        "expected_output_examples": _expected_output_examples(execution_context or {}),
        "failure_log_excerpt": _bounded((execution_context or {}).get("logs")),
        "task_constraints": safe_context,
        "other_attributed_causes": [
            evidence
            for evidence in (_step_evidence(trace.get_step(step_id)) for step_id in sibling_ids)
            if evidence is not None
        ],
        "prior_candidate_attempts": _prior_attempt_evidence(prior_repairs or []),
        "replay_scope": {
            "descendant_step_ids": descendants,
            "descendant_count": len(descendants),
            "requires_joint_plan": bool(sibling_ids),
            "safety_rule": "If required evidence or a dependency is unresolved, use full replay.",
        },
    }
