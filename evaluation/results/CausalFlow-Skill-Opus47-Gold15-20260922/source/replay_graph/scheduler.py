"""Graph-sliced replay scheduling with change pruning and safe fallback."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from replay_graph.builder import ConservativeGraphBuilder, step_node_id
from replay_graph.oracle import FullReplayOracle
from replay_graph.schema import (
    NodeKind,
    ReplayComparison,
    ReplayGraph,
    ReplayIntervention,
    ReplayResult,
    ReplayStatus,
    Verifier,
)


class SelectiveReplayScheduler:
    def __init__(self, oracle: Optional[FullReplayOracle] = None):
        self.oracle = oracle or FullReplayOracle()

    def replay(
        self,
        steps: Iterable[Dict[str, Any]],
        intervention: ReplayIntervention,
        *,
        graph: Optional[ReplayGraph] = None,
        verifier: Optional[Verifier] = None,
        calibrate_with_full: bool = True,
        fallback_on_mismatch: bool = True,
    ) -> ReplayComparison:
        materialized = [dict(step) for step in steps]
        graph = graph or ConservativeGraphBuilder().build(materialized)
        descendants = graph.descendants(step_node_id(intervention.step_id))
        selected_call_ids = {
            node.step_id
            for node_id, node in graph.nodes.items()
            if node_id in descendants
            and node.kind == NodeKind.STEP
            and node.step_type == "tool_call"
            and node.step_id is not None
        }
        selected_call_ids.add(intervention.step_id)

        selective = self.oracle.replay_selected(
            materialized,
            intervention,
            selected_call_ids=sorted(selected_call_ids),
            update_final=True,
            change_pruning=True,
            mode="selective",
            graph=graph,
            verifier=verifier,
        )

        full: Optional[ReplayResult] = None
        agreement: Optional[bool] = None
        returned = selective
        reduction: Optional[float] = None

        if calibrate_with_full or selective.status != ReplayStatus.COMPLETED:
            full = self.oracle.replay(
                materialized,
                intervention,
                graph=graph,
                verifier=verifier,
            )
            if selective.completed and full.completed:
                agreement = selective.observable_signature() == full.observable_signature()
                denominator = len(full.executed_step_ids)
                if denominator:
                    reduction = 1 - len(selective.executed_step_ids) / denominator
                if not agreement and fallback_on_mismatch:
                    full.fallback_used = True
                    full.diagnostics["fallback_reason"] = "selective/full mismatch"
                    returned = full
            elif full.completed:
                agreement = False
                if fallback_on_mismatch:
                    full.fallback_used = True
                    full.diagnostics["fallback_reason"] = (
                        selective.failure_reason or selective.status.value
                    )
                    returned = full
            else:
                agreement = None

        return ReplayComparison(
            selective=selective,
            full=full,
            agreement=agreement,
            returned=returned,
            replayed_call_reduction=reduction,
        )
