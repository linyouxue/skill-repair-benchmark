"""Core schema for replay-safe dependency graphs.

The graph is intentionally bipartite around produced resources:

    step -> versioned resource -> consuming step

This prevents equal values produced by different steps from being treated as
the same object.  Edge status is asymmetric: missing a dependency is unsafe,
while an extra ``may`` edge only costs additional replay work.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple


class NodeKind(str, Enum):
    STEP = "step"
    DECISION = "decision"
    RESOURCE = "resource"
    VERIFIER = "verifier"


class EdgeEvidence(str, Enum):
    OBSERVED = "observed"
    DECLARED = "declared"
    INFERRED = "inferred"
    INTERVENED = "intervened"


class EdgeStatus(str, Enum):
    MUST = "must"
    MAY = "may"
    TESTED_INDEPENDENT = "tested-independent"


class ReplayStatus(str, Enum):
    COMPLETED = "completed"
    FALLBACK_REQUIRED = "fallback-required"
    FAILED = "failed"


@dataclass(frozen=True)
class GraphNode:
    node_id: str
    kind: NodeKind
    step_id: Optional[int] = None
    step_type: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResourceVersion:
    resource_id: str
    producer_step_id: int
    resource_type: str
    value: Any
    version: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DependencyEdge:
    source: str
    target: str
    status: EdgeStatus
    evidence: EdgeEvidence
    reason: str
    replay_relevant: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResourceBinding:
    """Bind one numeric token occurrence in a consumer to producer candidates."""

    consumer_step_id: int
    token_index: int
    literal: str
    candidate_resource_ids: Tuple[str, ...]
    resolved_resource_id: Optional[str]
    evidence: EdgeEvidence

    @property
    def ambiguous(self) -> bool:
        return self.resolved_resource_id is None and len(self.candidate_resource_ids) > 1


@dataclass
class ReplayGraph:
    nodes: Dict[str, GraphNode] = field(default_factory=dict)
    resources: Dict[str, ResourceVersion] = field(default_factory=dict)
    edges: List[DependencyEdge] = field(default_factory=list)
    bindings: List[ResourceBinding] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_node(self, node: GraphNode) -> None:
        existing = self.nodes.get(node.node_id)
        if existing is not None and existing != node:
            raise ValueError(f"Conflicting node definition: {node.node_id}")
        self.nodes[node.node_id] = node

    def add_resource(self, resource: ResourceVersion) -> None:
        existing = self.resources.get(resource.resource_id)
        if existing is not None and existing != resource:
            raise ValueError(f"Conflicting resource definition: {resource.resource_id}")
        self.resources[resource.resource_id] = resource
        self.add_node(
            GraphNode(
                node_id=resource.resource_id,
                kind=NodeKind.RESOURCE,
                step_id=resource.producer_step_id,
                metadata={"resource_type": resource.resource_type},
            )
        )

    def add_edge(self, edge: DependencyEdge) -> None:
        if edge.source not in self.nodes or edge.target not in self.nodes:
            raise ValueError(f"Edge endpoints must exist: {edge.source} -> {edge.target}")
        if edge not in self.edges:
            self.edges.append(edge)

    def bindings_for(self, consumer_step_id: int) -> List[ResourceBinding]:
        return sorted(
            (binding for binding in self.bindings if binding.consumer_step_id == consumer_step_id),
            key=lambda binding: binding.token_index,
        )

    def descendants(
        self,
        root: str,
        statuses: Sequence[EdgeStatus] = (EdgeStatus.MUST, EdgeStatus.MAY),
        replay_only: bool = True,
    ) -> set[str]:
        allowed = set(statuses)
        adjacency: Dict[str, set[str]] = {}
        for edge in self.edges:
            if edge.status not in allowed:
                continue
            if replay_only and not edge.replay_relevant:
                continue
            adjacency.setdefault(edge.source, set()).add(edge.target)

        seen: set[str] = set()
        stack = [root]
        while stack:
            current = stack.pop()
            for child in adjacency.get(current, set()):
                if child not in seen:
                    seen.add(child)
                    stack.append(child)
        return seen

    def validate(self) -> None:
        for edge in self.edges:
            if edge.source not in self.nodes or edge.target not in self.nodes:
                raise ValueError(f"Unknown edge endpoint: {edge.source} -> {edge.target}")
        for binding in self.bindings:
            missing = [rid for rid in binding.candidate_resource_ids if rid not in self.resources]
            if missing:
                raise ValueError(f"Binding references unknown resources: {missing}")
            if (
                binding.resolved_resource_id is not None
                and binding.resolved_resource_id not in binding.candidate_resource_ids
            ):
                raise ValueError("resolved_resource_id must be one of candidate_resource_ids")

    def to_dict(self) -> Dict[str, Any]:
        def enum_value(value: Any) -> Any:
            if isinstance(value, Enum):
                return value.value
            if isinstance(value, dict):
                return {key: enum_value(item) for key, item in value.items()}
            if isinstance(value, (list, tuple)):
                return [enum_value(item) for item in value]
            return value

        return enum_value(
            {
                "nodes": [asdict(node) for node in self.nodes.values()],
                "resources": [asdict(resource) for resource in self.resources.values()],
                "edges": [asdict(edge) for edge in self.edges],
                "bindings": [asdict(binding) for binding in self.bindings],
                "metadata": self.metadata,
            }
        )


@dataclass(frozen=True)
class ReplayIntervention:
    step_id: int
    replacement_tool_args: Dict[str, Any]
    label: str = ""


@dataclass
class ReplayResult:
    status: ReplayStatus
    mode: str
    steps: List[Dict[str, Any]]
    final_answer: Optional[str]
    executed_step_ids: List[int] = field(default_factory=list)
    changed_resource_ids: List[str] = field(default_factory=list)
    unresolved_bindings: List[Dict[str, Any]] = field(default_factory=list)
    verifier_passed: Optional[bool] = None
    fallback_used: bool = False
    failure_reason: Optional[str] = None
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    @property
    def completed(self) -> bool:
        return self.status == ReplayStatus.COMPLETED

    def observable_signature(self) -> Tuple[Any, ...]:
        outputs = []
        for step in self.steps:
            if step.get("step_type") == "tool_response":
                outputs.append((step.get("step_id"), step.get("tool_output")))
        return tuple(outputs), self.final_answer, self.verifier_passed

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


@dataclass
class ReplayComparison:
    selective: ReplayResult
    full: Optional[ReplayResult]
    agreement: Optional[bool]
    returned: ReplayResult
    replayed_call_reduction: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selective": self.selective.to_dict(),
            "full": self.full.to_dict() if self.full is not None else None,
            "agreement": self.agreement,
            "returned": self.returned.to_dict(),
            "replayed_call_reduction": self.replayed_call_reduction,
        }


Verifier = Callable[[Optional[str]], bool]
