"""Deterministic full-tail replay oracle for fixed-plan GSM8K traces.

This executor deliberately refuses to guess when a changed numeric literal can
refer to multiple producer resources.  That makes ambiguity visible as a
fallback requirement instead of producing a silently corrupted replay.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from math_reexecutor import MathReexecutor
from replay_graph.builder import (
    ConservativeGraphBuilder,
    NUMBER_PATTERN,
    numeric_value,
    step_node_id,
)
from replay_graph.schema import (
    ReplayGraph,
    ReplayIntervention,
    ReplayResult,
    ReplayStatus,
    ResourceBinding,
    Verifier,
)


def _format_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


class AmbiguousBindingError(RuntimeError):
    def __init__(self, binding: ResourceBinding, candidate_values: Dict[str, Any]):
        super().__init__(
            f"step {binding.consumer_step_id} token {binding.literal!r} has "
            f"changed ambiguous producers"
        )
        self.binding = binding
        self.candidate_values = candidate_values


class FullReplayOracle:
    """Replay every deterministic calculator call after an intervention."""

    def __init__(self, evaluator: Optional[MathReexecutor] = None):
        self.evaluator = evaluator or MathReexecutor()

    def replay(
        self,
        steps: Iterable[Dict[str, Any]],
        intervention: ReplayIntervention,
        *,
        graph: Optional[ReplayGraph] = None,
        verifier: Optional[Verifier] = None,
    ) -> ReplayResult:
        materialized = [copy.deepcopy(step) for step in steps]
        selected_calls = {
            step["step_id"]
            for step in materialized
            if step.get("step_type") == "tool_call"
            and step["step_id"] >= intervention.step_id
        }
        return self.replay_selected(
            materialized,
            intervention,
            selected_call_ids=selected_calls,
            update_final=True,
            change_pruning=False,
            mode="full",
            graph=graph,
            verifier=verifier,
        )

    def replay_selected(
        self,
        steps: Iterable[Dict[str, Any]],
        intervention: ReplayIntervention,
        *,
        selected_call_ids: Sequence[int],
        update_final: bool,
        change_pruning: bool,
        mode: str,
        graph: Optional[ReplayGraph] = None,
        verifier: Optional[Verifier] = None,
    ) -> ReplayResult:
        changed_steps = sorted((copy.deepcopy(step) for step in steps), key=lambda s: s["step_id"])
        graph = graph or ConservativeGraphBuilder().build(changed_steps)
        by_id = {step["step_id"]: step for step in changed_steps}
        target = by_id.get(intervention.step_id)
        if target is None or target.get("step_type") != "tool_call":
            return self._failed(
                changed_steps,
                mode,
                f"intervention target {intervention.step_id} is not a tool_call",
            )

        responses_by_call = self._responses_by_call(changed_steps, graph)
        resources_by_response = {
            resource.producer_step_id: resource_id
            for resource_id, resource in graph.resources.items()
            if resource.resource_type == "tool_output"
        }
        original_values = {
            resource_id: numeric_value(resource.value)
            for resource_id, resource in graph.resources.items()
        }
        current_values = dict(original_values)
        selected = set(selected_call_ids)
        executed: List[int] = []
        changed_resources: set[str] = set()
        inferred_bindings_used = 0

        target["tool_args"] = copy.deepcopy(intervention.replacement_tool_args)

        for step in changed_steps:
            if step.get("step_type") != "tool_call" or step["step_id"] not in selected:
                continue
            call_id = step["step_id"]
            expression = str((step.get("tool_args") or {}).get("expression", ""))
            if call_id != intervention.step_id:
                try:
                    expression, input_changed, inferred_count = self._rewrite_consumer(
                        expression,
                        graph.bindings_for(call_id),
                        original_values,
                        current_values,
                    )
                    inferred_bindings_used += inferred_count
                except AmbiguousBindingError as exc:
                    return self._fallback_required(
                        changed_steps,
                        mode,
                        executed,
                        changed_resources,
                        exc,
                        inferred_bindings_used,
                    )
                if change_pruning and not input_changed:
                    continue
                step.setdefault("tool_args", {})["expression"] = expression

            result = self.evaluator.evaluate_expression(expression)
            if result is None:
                return self._failed(
                    changed_steps,
                    mode,
                    f"calculator could not evaluate step {call_id}: {expression!r}",
                    executed,
                    changed_resources,
                )
            executed.append(call_id)

            response_id = responses_by_call.get(call_id)
            if response_id is None:
                return self._failed(
                    changed_steps,
                    mode,
                    f"tool call step {call_id} has no response",
                    executed,
                    changed_resources,
                )
            resource_id = resources_by_response.get(response_id)
            response = by_id[response_id]
            original_numeric = original_values.get(resource_id) if resource_id is not None else None
            if original_numeric == float(result) and resource_id is not None:
                # Preserve the recorded representation (for example ``8.0``)
                # when replay did not change the value.  Formatting-only
                # differences must not be counted as state divergence.
                response["tool_output"] = graph.resources[resource_id].value
            else:
                response["tool_output"] = _format_number(result)
            if resource_id is not None:
                current_values[resource_id] = float(result)
                if original_values.get(resource_id) != float(result):
                    changed_resources.add(resource_id)
                else:
                    changed_resources.discard(resource_id)

        final_steps = [step for step in changed_steps if step.get("step_type") == "final_answer"]
        final_answer = None
        if final_steps:
            final_step = final_steps[-1]
            final_answer = str(final_step.get("text", final_step.get("answer", "")))
            final_selected = update_final and (
                mode == "full"
                or step_node_id(final_step["step_id"])
                in graph.descendants(step_node_id(intervention.step_id))
            )
            if final_selected:
                try:
                    rewritten, final_changed, inferred_count = self._rewrite_consumer(
                        final_answer,
                        graph.bindings_for(final_step["step_id"]),
                        original_values,
                        current_values,
                    )
                    inferred_bindings_used += inferred_count
                except AmbiguousBindingError as exc:
                    return self._fallback_required(
                        changed_steps,
                        mode,
                        executed,
                        changed_resources,
                        exc,
                        inferred_bindings_used,
                    )
                if final_changed:
                    final_step["text"] = rewritten
                    final_answer = rewritten

        verifier_passed = verifier(final_answer) if verifier is not None else None
        return ReplayResult(
            status=ReplayStatus.COMPLETED,
            mode=mode,
            steps=changed_steps,
            final_answer=final_answer,
            executed_step_ids=executed,
            changed_resource_ids=sorted(changed_resources),
            verifier_passed=verifier_passed,
            diagnostics={
                "inferred_bindings_used": inferred_bindings_used,
                "selected_call_count": len(selected),
                "change_pruning": change_pruning,
            },
        )

    def _responses_by_call(
        self,
        steps: List[Dict[str, Any]],
        graph: ReplayGraph,
    ) -> Dict[int, int]:
        mapping: Dict[int, int] = {}
        for resource in graph.resources.values():
            call_id = resource.metadata.get("call_step_id")
            if call_id is not None:
                mapping[int(call_id)] = resource.producer_step_id
        return mapping

    def _rewrite_consumer(
        self,
        text: str,
        bindings: Sequence[ResourceBinding],
        original_values: Dict[str, Optional[float]],
        current_values: Dict[str, Optional[float]],
    ) -> Tuple[str, bool, int]:
        by_index = {binding.token_index: binding for binding in bindings}
        pieces: List[str] = []
        cursor = 0
        changed = False
        inferred_count = 0

        for token_index, match in enumerate(NUMBER_PATTERN.finditer(text)):
            pieces.append(text[cursor : match.start()])
            replacement = match.group(0)
            binding = by_index.get(token_index)
            if binding is not None:
                candidate_values = {
                    resource_id: current_values.get(resource_id)
                    for resource_id in binding.candidate_resource_ids
                }
                if binding.resolved_resource_id is not None:
                    new_value = current_values.get(binding.resolved_resource_id)
                    old_value = original_values.get(binding.resolved_resource_id)
                    if new_value is not None and new_value != old_value:
                        replacement = _format_number(new_value)
                        changed = replacement != match.group(0)
                    if binding.evidence.value == "inferred":
                        inferred_count += 1
                else:
                    distinct = {value for value in candidate_values.values() if value is not None}
                    candidate_changed = any(
                        current_values.get(resource_id) != original_values.get(resource_id)
                        for resource_id in binding.candidate_resource_ids
                    )
                    if candidate_changed:
                        if len(distinct) == 1:
                            replacement = _format_number(distinct.pop())
                            changed = replacement != match.group(0)
                        else:
                            raise AmbiguousBindingError(binding, candidate_values)
            pieces.append(replacement)
            cursor = match.end()
        pieces.append(text[cursor:])
        return "".join(pieces), changed, inferred_count

    def _fallback_required(
        self,
        steps: List[Dict[str, Any]],
        mode: str,
        executed: Sequence[int],
        changed_resources: Sequence[str],
        error: AmbiguousBindingError,
        inferred_bindings_used: int,
    ) -> ReplayResult:
        return ReplayResult(
            status=ReplayStatus.FALLBACK_REQUIRED,
            mode=mode,
            steps=steps,
            final_answer=self._final_answer(steps),
            executed_step_ids=list(executed),
            changed_resource_ids=sorted(changed_resources),
            unresolved_bindings=[
                {
                    "consumer_step_id": error.binding.consumer_step_id,
                    "token_index": error.binding.token_index,
                    "literal": error.binding.literal,
                    "candidate_values": error.candidate_values,
                }
            ],
            failure_reason=str(error),
            diagnostics={"inferred_bindings_used": inferred_bindings_used},
        )

    def _failed(
        self,
        steps: List[Dict[str, Any]],
        mode: str,
        reason: str,
        executed: Sequence[int] = (),
        changed_resources: Sequence[str] = (),
    ) -> ReplayResult:
        return ReplayResult(
            status=ReplayStatus.FAILED,
            mode=mode,
            steps=steps,
            final_answer=self._final_answer(steps),
            executed_step_ids=list(executed),
            changed_resource_ids=sorted(changed_resources),
            failure_reason=reason,
        )

    @staticmethod
    def _final_answer(steps: Sequence[Dict[str, Any]]) -> Optional[str]:
        final_steps = [step for step in steps if step.get("step_type") == "final_answer"]
        if not final_steps:
            return None
        step = final_steps[-1]
        return str(step.get("text", step.get("answer", "")))
