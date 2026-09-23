"""Conservative replay-graph construction for recorded agent traces."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

from replay_graph.schema import (
    DependencyEdge,
    EdgeEvidence,
    EdgeStatus,
    GraphNode,
    NodeKind,
    ReplayGraph,
    ResourceBinding,
    ResourceVersion,
)


NUMBER_PATTERN = re.compile(r"(?<![\w.])-?\d+(?:,\d{3})*(?:\.\d+)?(?![\w.])")


def step_node_id(step_id: int) -> str:
    return f"step:{step_id}"


def tool_output_resource_id(response_step_id: int) -> str:
    return f"resource:step:{response_step_id}:tool_output:v1"


def numeric_value(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def numeric_tokens(text: Any) -> List[Tuple[int, str, float]]:
    tokens: List[Tuple[int, str, float]] = []
    for token_index, match in enumerate(NUMBER_PATTERN.finditer(str(text or ""))):
        value = numeric_value(match.group(0))
        if value is not None:
            tokens.append((token_index, match.group(0), value))
    return tokens


class ConservativeGraphBuilder:
    """Build observed structure plus all plausible resource-read candidates.

    Equal resource values are never merged.  If multiple earlier resources can
    explain one literal, every candidate edge is retained as ``may`` and the
    binding remains unresolved.  A replay engine must then fall back instead of
    silently choosing the most recent producer.

    Declared history dependencies are kept for audit but excluded from the
    fixed-plan calculator replay slice.  They become replay-relevant only when
    a future executor also re-runs LLM decisions.
    """

    def build(self, steps: Iterable[Dict[str, Any]]) -> ReplayGraph:
        ordered = sorted((dict(step) for step in steps), key=lambda step: step["step_id"])
        graph = ReplayGraph(
            metadata={
                "builder": self.__class__.__name__,
                "intervention_family": "fixed-plan deterministic tool replay",
            }
        )

        for step in ordered:
            graph.add_node(
                GraphNode(
                    node_id=step_node_id(step["step_id"]),
                    kind=NodeKind.STEP,
                    step_id=step["step_id"],
                    step_type=step.get("step_type"),
                )
            )

        self._add_declared_edges(graph, ordered)
        response_resources = self._add_tool_response_resources(graph, ordered)
        self._add_resource_bindings(graph, ordered, response_resources)
        graph.validate()
        return graph

    def _add_declared_edges(self, graph: ReplayGraph, steps: List[Dict[str, Any]]) -> None:
        ids = {step["step_id"] for step in steps}
        for step in steps:
            target = step_node_id(step["step_id"])
            for dependency in step.get("dependencies") or []:
                if dependency not in ids or dependency >= step["step_id"]:
                    continue
                graph.add_edge(
                    DependencyEdge(
                        source=step_node_id(dependency),
                        target=target,
                        status=EdgeStatus.MAY,
                        evidence=EdgeEvidence.DECLARED,
                        reason="trace-declared history dependency",
                        replay_relevant=False,
                    )
                )

    def _add_tool_response_resources(
        self,
        graph: ReplayGraph,
        steps: List[Dict[str, Any]],
    ) -> Dict[int, str]:
        response_resources: Dict[int, str] = {}
        call_ids = {
            step["step_id"] for step in steps if step.get("step_type") == "tool_call"
        }
        last_call: Optional[int] = None

        for step in steps:
            step_id = step["step_id"]
            if step.get("step_type") == "tool_call":
                last_call = step_id
                continue
            if step.get("step_type") != "tool_response":
                continue

            declared_calls = [
                dependency
                for dependency in step.get("dependencies") or []
                if dependency in call_ids and dependency < step_id
            ]
            call_id = max(declared_calls) if declared_calls else last_call
            if call_id is not None:
                graph.add_edge(
                    DependencyEdge(
                        source=step_node_id(call_id),
                        target=step_node_id(step_id),
                        status=EdgeStatus.MUST,
                        evidence=EdgeEvidence.OBSERVED,
                        reason="tool response belongs to its tool call",
                    )
                )

            explicit_writes = list(step.get("resource_writes") or [])
            resource_id = explicit_writes[0] if explicit_writes else tool_output_resource_id(step_id)
            resource = ResourceVersion(
                resource_id=resource_id,
                producer_step_id=step_id,
                resource_type="tool_output",
                value=step.get("tool_output"),
                metadata={"tool_name": step.get("tool_name"), "call_step_id": call_id},
            )
            graph.add_resource(resource)
            response_resources[step_id] = resource_id
            graph.add_edge(
                DependencyEdge(
                    source=step_node_id(step_id),
                    target=resource_id,
                    status=EdgeStatus.MUST,
                    evidence=EdgeEvidence.OBSERVED,
                    reason="tool response produced this resource version",
                )
            )
        return response_resources

    def _consumer_text(self, step: Dict[str, Any]) -> Optional[str]:
        if step.get("step_type") == "tool_call":
            expression = (step.get("tool_args") or {}).get("expression")
            return str(expression) if expression is not None else None
        if step.get("step_type") == "final_answer":
            return str(step.get("text", step.get("answer", "")))
        return None

    def _add_resource_bindings(
        self,
        graph: ReplayGraph,
        steps: List[Dict[str, Any]],
        response_resources: Dict[int, str],
    ) -> None:
        producers: Dict[float, List[str]] = defaultdict(list)

        for step in steps:
            step_id = step["step_id"]
            consumer_text = self._consumer_text(step)
            if consumer_text is not None:
                explicit_reads = tuple(step.get("resource_reads") or ())
                for token_index, literal, value in numeric_tokens(consumer_text):
                    explicit_candidates = tuple(
                        resource_id
                        for resource_id in explicit_reads
                        if resource_id in graph.resources
                        and numeric_value(graph.resources[resource_id].value) == value
                    )
                    if explicit_candidates:
                        candidates = explicit_candidates
                        evidence = EdgeEvidence.OBSERVED
                    else:
                        candidates = tuple(producers.get(value, ()))
                        evidence = EdgeEvidence.INFERRED
                    if not candidates:
                        continue

                    resolved = candidates[0] if len(candidates) == 1 else None
                    graph.bindings.append(
                        ResourceBinding(
                            consumer_step_id=step_id,
                            token_index=token_index,
                            literal=literal,
                            candidate_resource_ids=candidates,
                            resolved_resource_id=resolved,
                            evidence=evidence,
                        )
                    )
                    for resource_id in candidates:
                        graph.add_edge(
                            DependencyEdge(
                                source=resource_id,
                                target=step_node_id(step_id),
                                status=(
                                    EdgeStatus.MUST
                                    if evidence == EdgeEvidence.OBSERVED and len(candidates) == 1
                                    else EdgeStatus.MAY
                                ),
                                evidence=evidence,
                                reason=f"numeric token {literal!r} may read this resource version",
                                metadata={"token_index": token_index, "literal": literal},
                            )
                        )

            resource_id = response_resources.get(step_id)
            if resource_id is not None:
                value = numeric_value(graph.resources[resource_id].value)
                if value is not None:
                    producers[value].append(resource_id)
