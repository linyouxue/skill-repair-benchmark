"""Command-line inspection of a SkillsBench rollout directory."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from replay_graph.schema import EdgeEvidence, EdgeStatus
from skillsbench_replay.atif import load_run
from skillsbench_replay.graph import (
    SkillsBenchGraphBuilder,
    infer_task_workspace,
    infer_verifier_reads,
    resource_ids_for_paths,
)
from skillsbench_replay.planner import ReplayPlanner


def analyze(run_dir: Path, task_dir: Path | None = None) -> dict:
    parsed = load_run(run_dir)
    verifier_reads = (
        infer_verifier_reads(task_dir / "verifier") if task_dir is not None else ()
    )
    workspace_root = infer_task_workspace(task_dir) if task_dir is not None else None
    graph = SkillsBenchGraphBuilder().build(
        parsed.events,
        verifier_reads=verifier_reads,
        workspace_root=workspace_root,
    )
    initial_path_slices: dict[str, dict] = {}
    for resource in graph.resources.values():
        path = resource.metadata.get("path")
        if not resource.metadata.get("initial") or not isinstance(path, str):
            continue
        resource_ids = resource_ids_for_paths(graph, [path])
        selection = ReplayPlanner().plan(graph, resource_ids)
        selected_steps = list(selection.selected_step_ids)
        initial_path_slices[path] = {
            "selected_steps": selected_steps,
            "command_reduction": (
                1 - len(selected_steps) / len(parsed.events) if parsed.events else None
            ),
            "verifier_reachable": selection.verifier_reachable,
            "fallback_required": selection.fallback_required,
            "fallback_reason": selection.reason,
        }
    argument_sources = Counter(event.argument_source for event in parsed.events)
    return {
        "run": parsed.to_dict(),
        "summary": {
            "command_events": len(parsed.events),
            "replayable_events": sum(event.replayable for event in parsed.events),
            "argument_sources": dict(argument_sources),
            "graph_nodes": len(graph.nodes),
            "graph_resources": len(graph.resources),
            "graph_edges": len(graph.edges),
            "must_edges": sum(edge.status == EdgeStatus.MUST for edge in graph.edges),
            "may_edges": sum(edge.status == EdgeStatus.MAY for edge in graph.edges),
            "observed_edges": sum(
                edge.evidence == EdgeEvidence.OBSERVED for edge in graph.edges
            ),
            "inferred_edges": sum(
                edge.evidence == EdgeEvidence.INFERRED for edge in graph.edges
            ),
            "verifier_referenced_paths": list(verifier_reads),
            "workspace_root": workspace_root,
        },
        "graph": graph.to_dict(),
        "initial_path_slices": initial_path_slices,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--task-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = analyze(
        args.run_dir.resolve(), args.task_dir.resolve() if args.task_dir else None
    )
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized)
    else:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
