"""Build a non-serial resource-version graph from SkillsBench commands."""

from __future__ import annotations

import ast
import hashlib
import re
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, Optional, Sequence

from replay_graph.builder import step_node_id
from replay_graph.schema import (
    DependencyEdge,
    EdgeEvidence,
    EdgeStatus,
    GraphNode,
    NodeKind,
    ReplayGraph,
    ResourceVersion,
)
from skillsbench_replay.schema import CommandEvent
from skillsbench_replay.snapshot import WorkspaceSnapshot


ABSOLUTE_PATH_RE = re.compile(r"(?P<quote>['\"]?)(?P<path>/[A-Za-z0-9_./-]+)(?P=quote)")
WORKSPACE_PREFIXES = (
    "/app/",
    "/root/",
    "/home/",
    "/workspace/",
    "/output/",
    "/data/",
)


def file_resource_id(path: str, version: int) -> str:
    digest = hashlib.sha1(path.encode("utf-8"), usedforsecurity=False).hexdigest()[:12]
    return f"resource:file:{digest}:v{version}"


class SkillsBenchGraphBuilder:
    """Create file-flow edges without inventing a global sequential chain."""

    def build(
        self,
        events: Iterable[CommandEvent],
        *,
        initial_snapshot: Optional[WorkspaceSnapshot] = None,
        verifier_reads: Sequence[str] = (),
        workspace_root: Optional[str] = None,
    ) -> ReplayGraph:
        ordered = sorted(events, key=lambda event: event.step_id)
        normalized_workspace = (
            PurePosixPath(workspace_root).as_posix() if workspace_root else None
        )
        graph = ReplayGraph(
            metadata={
                "builder": self.__class__.__name__,
                "domain": "skillsbench",
                "dependency_model": "versioned-file-flow",
                "global_sequential_edges": False,
                "workspace_root": normalized_workspace,
            }
        )
        latest: Dict[str, str] = {}
        versions: dict[str, int] = defaultdict(int)

        for event in ordered:
            graph.add_node(
                GraphNode(
                    node_id=step_node_id(event.step_id),
                    kind=NodeKind.STEP,
                    step_id=event.step_id,
                    step_type="command",
                    metadata={
                        "tool_call_id": event.tool_call_id,
                        "kind": event.kind,
                        "command": event.command,
                        "argument_source": event.argument_source,
                        "replayable": event.replayable,
                    },
                )
            )

        for event in ordered:
            observed_reads = {
                canonical_file_path(path, normalized_workspace)
                for path in event.observed_reads
            }
            observed = {
                canonical_file_path(path, normalized_workspace)
                for path in event.observed_writes
            }
            reads = tuple(
                dict.fromkeys(
                    canonical_file_path(path, normalized_workspace)
                    for path in (*event.inferred_reads, *event.observed_reads)
                )
            )
            writes = tuple(
                dict.fromkeys(
                    canonical_file_path(path, normalized_workspace)
                    for path in (*event.inferred_writes, *event.observed_writes)
                )
            )

            for path in reads:
                resource_id = latest.get(path)
                if resource_id is None:
                    resource_id = self._add_initial_resource(
                        graph,
                        path,
                        versions,
                        initial_snapshot,
                        normalized_workspace,
                    )
                    latest[path] = resource_id
                graph.add_edge(
                    DependencyEdge(
                        source=resource_id,
                        target=step_node_id(event.step_id),
                        status=(
                            EdgeStatus.MUST
                            if path in observed_reads
                            else EdgeStatus.MAY
                        ),
                        evidence=(
                            EdgeEvidence.OBSERVED
                            if path in observed_reads
                            else EdgeEvidence.INFERRED
                        ),
                        reason=(
                            f"runtime audit observed read from {path}"
                            if path in observed_reads
                            else f"command text may read {path}"
                        ),
                        metadata={"path": path},
                    )
                )

            for path in writes:
                versions[path] += 1
                resource_id = file_resource_id(path, versions[path])
                is_observed = path in observed
                graph.add_resource(
                    ResourceVersion(
                        resource_id=resource_id,
                        producer_step_id=event.step_id,
                        resource_type="file",
                        # Per-command snapshots currently prove that a write
                        # occurred. A later sidecar can also supply this version's
                        # exact post-write hash; until then, do not reuse the
                        # initial snapshot hash as if it were the new value.
                        value=None,
                        version=versions[path],
                        metadata={
                            "path": path,
                            "change": "write",
                            "observed": is_observed,
                        },
                    )
                )
                graph.add_edge(
                    DependencyEdge(
                        source=step_node_id(event.step_id),
                        target=resource_id,
                        status=EdgeStatus.MUST if is_observed else EdgeStatus.MAY,
                        evidence=(
                            EdgeEvidence.OBSERVED
                            if is_observed
                            else EdgeEvidence.INFERRED
                        ),
                        reason=(
                            f"workspace snapshot observed write to {path}"
                            if is_observed
                            else f"command text may write {path}"
                        ),
                        metadata={"path": path},
                    )
                )
                latest[path] = resource_id

        self._add_verifier(graph, latest, verifier_reads)
        graph.metadata["file_latest_resources"] = dict(latest)
        graph.metadata["command_count"] = len(ordered)
        graph.validate()
        return graph

    def _add_initial_resource(
        self,
        graph: ReplayGraph,
        path: str,
        versions: dict[str, int],
        snapshot: Optional[WorkspaceSnapshot],
        workspace_root: Optional[str],
    ) -> str:
        resource_id = file_resource_id(path, 0)
        value = None
        snapshot_key = path.lstrip("./")
        if workspace_root and path.startswith(f"{workspace_root.rstrip('/')}/"):
            snapshot_key = path.removeprefix(f"{workspace_root.rstrip('/')}/")
        if snapshot is not None and snapshot_key in snapshot.files:
            value = snapshot.files[snapshot_key].sha256
        graph.add_resource(
            ResourceVersion(
                resource_id=resource_id,
                producer_step_id=0,
                resource_type="file",
                value=value,
                version=0,
                metadata={"path": path, "initial": True},
            )
        )
        versions[path] = 0
        return resource_id

    def _add_verifier(
        self,
        graph: ReplayGraph,
        latest: Dict[str, str],
        verifier_reads: Sequence[str],
    ) -> None:
        if not verifier_reads:
            return
        verifier_id = "verifier:skillsbench"
        graph.add_node(
            GraphNode(
                node_id=verifier_id,
                kind=NodeKind.VERIFIER,
                step_type="skillsbench_verifier",
            )
        )
        for path in dict.fromkeys(verifier_reads):
            resource_ids = [latest[path]] if path in latest else [
                resource_id
                for candidate_path, resource_id in latest.items()
                if candidate_path.startswith(path)
            ]
            if not resource_ids:
                continue
            for resource_id in dict.fromkeys(resource_ids):
                graph.add_edge(
                    DependencyEdge(
                        source=resource_id,
                        target=verifier_id,
                        status=EdgeStatus.MAY,
                        evidence=EdgeEvidence.INFERRED,
                        reason=f"verifier source references {path}",
                        metadata={"path": path},
                    )
                )


def infer_verifier_reads(verifier_dir: str | Path) -> tuple[str, ...]:
    """Extract absolute file literals from verifier source as conservative hints."""

    root = Path(verifier_dir)
    paths: list[str] = []
    if not root.exists():
        return ()
    for source in sorted(root.rglob("*")):
        if not source.is_file() or source.suffix not in {".py", ".sh"}:
            continue
        try:
            text = source.read_text(errors="replace")
        except OSError:
            continue
        paths.extend(
            path
            for match in ABSOLUTE_PATH_RE.finditer(text)
            if (path := match.group("path")).startswith(WORKSPACE_PREFIXES)
        )
        if source.suffix == ".py":
            paths.extend(_infer_python_path_constants(text))
    return tuple(dict.fromkeys(PurePosixPath(path).as_posix() for path in paths))


def _infer_python_path_constants(text: str) -> tuple[str, ...]:
    """Resolve simple ``Path('/app') / 'file'`` verifier constants.

    SkillsBench verifiers commonly define an output directory first and derive
    the actual graded file with pathlib's division operator.  Literal-only
    extraction sees the directory but misses the file, which severs the graph's
    output-to-verifier edge.  This evaluator intentionally supports only static
    constants and never executes verifier code.
    """

    try:
        tree = ast.parse(text)
    except SyntaxError:
        return ()
    values: dict[str, str] = {}
    discovered: list[str] = []

    def evaluate(node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.Name):
            return values.get(node.id)
        if isinstance(node, ast.Call) and node.args:
            function_name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr
                if isinstance(node.func, ast.Attribute)
                else ""
            )
            if function_name in {"Path", "PurePath", "PurePosixPath"}:
                return evaluate(node.args[0])
            if function_name == "join":
                parts = [evaluate(argument) for argument in node.args]
                if parts and all(part is not None for part in parts):
                    return PurePosixPath(parts[0], *parts[1:]).as_posix()
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            left, right = evaluate(node.left), evaluate(node.right)
            if left is not None and right is not None:
                return (PurePosixPath(left) / right).as_posix()
        return None

    for statement in tree.body:
        targets: list[ast.expr] = []
        value_node: ast.AST | None = None
        if isinstance(statement, ast.Assign):
            targets = list(statement.targets)
            value_node = statement.value
        elif isinstance(statement, ast.AnnAssign):
            targets = [statement.target]
            value_node = statement.value
        if value_node is None:
            continue
        value = evaluate(value_node)
        if value is None:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                values[target.id] = value
        if value.startswith(WORKSPACE_PREFIXES):
            discovered.append(PurePosixPath(value).as_posix())
    return tuple(dict.fromkeys(discovered))


def infer_task_workspace(task_dir: str | Path) -> Optional[str]:
    """Read the task workdir, preferring explicit metadata over Dockerfile."""

    root = Path(task_dir)
    task_md = root / "task.md"
    if task_md.exists():
        text = task_md.read_text(errors="replace")
        match = re.search(r"(?m)^\s*workdir:\s*['\"]?([^\s'\"]+)", text)
        if match and match.group(1).startswith("/"):
            return PurePosixPath(match.group(1)).as_posix()
    dockerfile = root / "environment" / "Dockerfile"
    if dockerfile.exists():
        matches = re.findall(
            r"(?mi)^\s*WORKDIR\s+([^\s#]+)", dockerfile.read_text(errors="replace")
        )
        if matches and matches[-1].startswith("/"):
            return PurePosixPath(matches[-1]).as_posix()
    return None


def canonical_file_path(path: str, workspace_root: Optional[str]) -> str:
    pure = PurePosixPath(path)
    if pure.is_absolute() or not workspace_root:
        return pure.as_posix()
    return (PurePosixPath(workspace_root) / pure).as_posix()


def resource_ids_for_paths(graph: ReplayGraph, paths: Iterable[str]) -> list[str]:
    workspace_root = graph.metadata.get("workspace_root")
    wanted = {
        canonical_file_path(
            path, workspace_root if isinstance(workspace_root, str) else None
        )
        for path in paths
    }
    initial = [
        resource.resource_id
        for resource in graph.resources.values()
        if resource.metadata.get("path") in wanted and resource.metadata.get("initial")
    ]
    return sorted(initial)
