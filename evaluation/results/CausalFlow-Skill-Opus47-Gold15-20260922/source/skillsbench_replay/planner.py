"""Graph slicing plus a guarded local runner for deterministic smoke tests."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional

from replay_graph.schema import NodeKind, ReplayGraph
from skillsbench_replay.graph import resource_ids_for_paths
from skillsbench_replay.schema import CommandEvent, ReplayExperiment, ReplayRun
from skillsbench_replay.shell_io import local_replay_safety_reason
from skillsbench_replay.snapshot import WorkspaceSnapshot


Verifier = Callable[[Path], bool]


@dataclass(frozen=True)
class ReplaySelection:
    selected_step_ids: tuple[int, ...]
    regenerate_decision_step_ids: tuple[int, ...]
    verifier_reachable: bool
    fallback_required: bool
    reason: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class ReplayPlanner:
    def plan(
        self,
        graph: ReplayGraph,
        changed_resource_ids: Iterable[str],
        *,
        supports_model_regeneration: bool = False,
    ) -> ReplaySelection:
        changed = tuple(dict.fromkeys(changed_resource_ids))
        descendants: set[str] = set()
        for resource_id in changed:
            descendants.update(graph.descendants(resource_id))
        selected = tuple(
            sorted(
                node.step_id
                for node_id, node in graph.nodes.items()
                if node_id in descendants
                and node.kind == NodeKind.STEP
                and node.step_type == "command"
                and node.step_id is not None
            )
        )
        regenerate = tuple(
            sorted(
                node.step_id
                for node_id, node in graph.nodes.items()
                if node_id in descendants
                and node.kind == NodeKind.DECISION
                and node.step_id is not None
            )
        )
        verifier_ids = {
            node_id
            for node_id, node in graph.nodes.items()
            if node.kind == NodeKind.VERIFIER
        }
        verifier_reachable = bool(verifier_ids & descendants)
        if not changed:
            reason = "changed resource is absent from the graph"
        elif not verifier_ids:
            reason = "graph has no verifier node"
        elif not verifier_reachable:
            reason = "slice does not reach verifier; semantic dependency may be missing"
        elif regenerate and not supports_model_regeneration:
            reason = (
                "slice includes an LLM decision; command-only replay cannot "
                "regenerate the affected command"
            )
        else:
            reason = None
        return ReplaySelection(
            selected_step_ids=selected,
            regenerate_decision_step_ids=regenerate,
            verifier_reachable=verifier_reachable,
            fallback_required=reason is not None,
            reason=reason,
        )

    def selected_steps(
        self,
        graph: ReplayGraph,
        changed_resource_ids: Iterable[str],
    ) -> list[int]:
        return list(self.plan(graph, changed_resource_ids).selected_step_ids)

    def safe_selected_steps(
        self,
        graph: ReplayGraph,
        changed_resource_ids: Iterable[str],
        all_step_ids: Iterable[int],
    ) -> list[int]:
        selection = self.plan(graph, changed_resource_ids)
        if selection.fallback_required:
            return sorted(dict.fromkeys(all_step_ids))
        return list(selection.selected_step_ids)


class LocalReplayRunner:
    """Replay only allowlisted relative-path commands in disposable directories.

    Real SkillsBench tasks must use Docker. This runner exists to validate graph
    semantics cheaply and refuses absolute paths, deletions, network commands,
    package managers, heredocs, and unknown executables.
    """

    def __init__(
        self,
        initial_workspace: str | Path,
        events: Iterable[CommandEvent],
        graph: ReplayGraph,
        *,
        verifier: Optional[Verifier] = None,
    ) -> None:
        self.initial_workspace = Path(initial_workspace).resolve()
        self.events = sorted(events, key=lambda event: event.step_id)
        self.graph = graph
        self.verifier = verifier
        self._validate_commands()

    def compare(self, intervention_files: Dict[str, bytes | str]) -> ReplayExperiment:
        original = self._run(mode="original", intervention_files={}, selected=None)
        full = self._run(
            mode="full", intervention_files=intervention_files, selected=None
        )

        changed_ids = resource_ids_for_paths(self.graph, intervention_files)
        selected = set(
            ReplayPlanner().safe_selected_steps(
                self.graph,
                changed_ids,
                (event.step_id for event in self.events),
            )
        )
        original_workspace = Path(original.workspace)
        try:
            selective = self._run(
                mode="selective",
                intervention_files=intervention_files,
                selected=selected,
                base_workspace=original_workspace,
            )
        finally:
            if original_workspace.name.startswith("causalflow-skillsbench-original-"):
                shutil.rmtree(original_workspace, ignore_errors=True)
        agreement = full.observable_signature() == selective.observable_signature()
        reduction = None
        if full.executed_step_ids:
            reduction = 1 - len(selective.executed_step_ids) / len(
                full.executed_step_ids
            )
        return ReplayExperiment(
            full=full,
            selective=selective,
            agreement=agreement,
            command_reduction=reduction,
        )

    def _run(
        self,
        *,
        mode: str,
        intervention_files: Dict[str, bytes | str],
        selected: Optional[set[int]],
        base_workspace: Optional[Path] = None,
    ) -> ReplayRun:
        # macOS commonly exposes /var as a symlink to /private/var. Resolve the
        # temporary root before doing descendant checks so a valid relative
        # intervention is not mistaken for a workspace escape.
        workspace = Path(
            tempfile.mkdtemp(prefix=f"causalflow-skillsbench-{mode}-")
        ).resolve()
        source = base_workspace or self.initial_workspace
        shutil.copytree(source, workspace, dirs_exist_ok=True)
        for relative, content in intervention_files.items():
            target = self._safe_target(workspace, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                target.write_bytes(content)
            else:
                target.write_text(content)

        executed: list[int] = []
        failure_reason: Optional[str] = None
        for event in self.events:
            if selected is not None and event.step_id not in selected:
                continue
            if not event.command:
                failure_reason = f"step {event.step_id} has no command"
                break
            result = subprocess.run(
                ["/bin/sh", "-lc", event.command],
                cwd=workspace,
                env={**os.environ, "HOME": str(workspace)},
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
            executed.append(event.step_id)
            if result.returncode != 0:
                failure_reason = (
                    f"step {event.step_id} returned {result.returncode}: "
                    f"{result.stderr[-500:]}"
                )
                break
        snapshot = WorkspaceSnapshot.capture(workspace)
        verifier_passed = (
            self.verifier(workspace)
            if self.verifier and failure_reason is None
            else None
        )
        return ReplayRun(
            mode=mode,
            executed_step_ids=executed,
            manifest=snapshot.manifest(),
            verifier_passed=verifier_passed,
            workspace=str(workspace),
            failure_reason=failure_reason,
        )

    def _validate_commands(self) -> None:
        for event in self.events:
            if not event.command:
                raise ValueError(f"step {event.step_id} is not replayable")
            reason = local_replay_safety_reason(event.command)
            if reason:
                raise ValueError(
                    f"step {event.step_id} requires Docker replay: {reason}"
                )

    @staticmethod
    def _safe_target(workspace: Path, relative: str) -> Path:
        candidate = (workspace / relative).resolve()
        if candidate != workspace and workspace not in candidate.parents:
            raise ValueError(f"intervention escapes workspace: {relative}")
        return candidate
