"""Add sparse, auditable semantic-influence edges to a file-flow graph.

File tracing can prove that a command read a skill document, but the skill is
then carried in the language model's context rather than copied into a later
shell argument.  This module represents that missing relation conservatively:

    skill file -> later decision/command

Semantic edges are always ``may`` edges.  They begin as inferred proposals and
can carry intervention evidence later, but they are not promoted to hard
dependencies until repeated experiments validate the exact boundary.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Sequence

from replay_graph.schema import (
    DependencyEdge,
    EdgeEvidence,
    EdgeStatus,
    GraphNode,
    NodeKind,
    ReplayGraph,
)
from skillsbench_replay.graph import resource_ids_for_paths


SEMANTIC_DEPENDENCY_TYPE = "semantic-influence"


def decision_node_id(step_id: int) -> str:
    return f"decision:{step_id}"


@dataclass(frozen=True)
class SemanticDependency:
    """One model- or human-proposed skill-to-command dependency."""

    source_path: str
    target_step_id: int
    relation: str
    confidence: float
    reason: str
    shared_concepts: tuple[str, ...] = ()
    judge: str = "unspecified"

    @classmethod
    def from_dict(cls, payload: dict) -> "SemanticDependency":
        return cls(
            source_path=str(payload["source_path"]),
            target_step_id=int(payload["target_step_id"]),
            relation=str(payload.get("relation", "supporting")),
            confidence=float(payload.get("confidence", 0.0)),
            reason=str(payload.get("reason", "")),
            shared_concepts=tuple(
                str(item) for item in payload.get("shared_concepts", ())
            ),
            judge=str(payload.get("judge", "unspecified")),
        )

    def to_dict(self) -> dict:
        return asdict(self)


def add_semantic_dependencies(
    graph: ReplayGraph,
    dependencies: Iterable[SemanticDependency],
    *,
    minimum_confidence: float = 0.5,
    allowed_relations: Sequence[str] = ("required", "supporting"),
    evidence: EdgeEvidence = EdgeEvidence.INFERRED,
) -> list[DependencyEdge]:
    """Attach accepted semantic edges and return the edges actually added.

    A proposal is accepted only if its source is an initial file resource, its
    target is a later command than the observed/inferred skill-read command,
    and it clears the requested confidence/relation filter.  These checks stop
    a language-model judge from silently recreating a global sequential chain.
    ``INTERVENED`` evidence can be supplied after an ablation changes the
    verifier outcome; the edge remains ``may`` until repeated interventions
    identify and validate the exact downstream command boundary.
    """

    accepted_relations = set(allowed_relations)
    added: list[DependencyEdge] = []
    rejected: list[dict] = []

    for dependency in dependencies:
        rejection = _validate_dependency(
            graph,
            dependency,
            minimum_confidence=minimum_confidence,
            allowed_relations=accepted_relations,
        )
        if rejection is not None:
            rejected.append({**dependency.to_dict(), "rejection": rejection})
            continue

        source_id = resource_ids_for_paths(graph, [dependency.source_path])[0]
        command_id = f"step:{dependency.target_step_id}"
        target_id = decision_node_id(dependency.target_step_id)
        graph.add_node(
            GraphNode(
                node_id=target_id,
                kind=NodeKind.DECISION,
                step_id=dependency.target_step_id,
                step_type="llm_command_decision",
                metadata={"materialized_command": command_id},
            )
        )
        graph.add_edge(
            DependencyEdge(
                source=target_id,
                target=command_id,
                status=EdgeStatus.MUST,
                evidence=EdgeEvidence.OBSERVED,
                reason="recorded LLM decision materialized this command",
                metadata={"dependency_type": "decision-materialization"},
            )
        )
        edge = DependencyEdge(
            source=source_id,
            target=target_id,
            status=EdgeStatus.MAY,
            evidence=evidence,
            reason=dependency.reason,
            metadata={
                "dependency_type": SEMANTIC_DEPENDENCY_TYPE,
                "source_path": dependency.source_path,
                "relation": dependency.relation,
                "confidence": dependency.confidence,
                "shared_concepts": list(dependency.shared_concepts),
                "judge": dependency.judge,
                "evidence_stage": evidence.value,
            },
        )
        before = len(graph.edges)
        graph.add_edge(edge)
        if len(graph.edges) > before:
            added.append(edge)

    if added:
        graph.metadata["dependency_model"] = (
            "hybrid-versioned-file-flow+semantic-influence"
        )
    semantic_edges = [
        edge
        for edge in graph.edges
        if edge.metadata.get("dependency_type") == SEMANTIC_DEPENDENCY_TYPE
    ]
    graph.metadata["semantic_edge_count"] = len(semantic_edges)
    graph.metadata["intervened_semantic_edge_count"] = sum(
        edge.evidence == EdgeEvidence.INTERVENED for edge in semantic_edges
    )
    graph.metadata["semantic_decision_node_count"] = sum(
        node.kind == NodeKind.DECISION for node in graph.nodes.values()
    )
    graph.metadata["semantic_edge_rejections"] = rejected
    graph.validate()
    return added


def _validate_dependency(
    graph: ReplayGraph,
    dependency: SemanticDependency,
    *,
    minimum_confidence: float,
    allowed_relations: set[str],
) -> str | None:
    if dependency.relation not in allowed_relations:
        return f"relation {dependency.relation!r} is not replay-relevant"
    if not 0.0 <= dependency.confidence <= 1.0:
        return "confidence must be between 0 and 1"
    if dependency.confidence < minimum_confidence:
        return f"confidence is below {minimum_confidence}"

    source_ids = resource_ids_for_paths(graph, [dependency.source_path])
    if len(source_ids) != 1:
        return "source path does not resolve to exactly one initial resource"
    source_id = source_ids[0]

    target_id = f"step:{dependency.target_step_id}"
    target = graph.nodes.get(target_id)
    if target is None or target.kind != NodeKind.STEP:
        return "target is not a known step"
    if target.step_type != "command":
        return "target is not a command step"

    read_steps = sorted(
        node.step_id
        for edge in graph.edges
        if edge.source == source_id
        and (node := graph.nodes.get(edge.target)) is not None
        and node.kind == NodeKind.STEP
        and node.step_id is not None
        and edge.metadata.get("dependency_type") != SEMANTIC_DEPENDENCY_TYPE
    )
    if not read_steps:
        return "source skill has no recorded read step"
    if dependency.target_step_id <= read_steps[0]:
        return "target does not occur after the skill read"
    return None
