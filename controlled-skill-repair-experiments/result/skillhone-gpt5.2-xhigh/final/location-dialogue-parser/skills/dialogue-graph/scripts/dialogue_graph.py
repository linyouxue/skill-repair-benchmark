"""dialogue_graph

A tiny, dependency-light library for building, validating, serializing, and
visualizing dialogue graphs.

Key conventions
---------------
- Nodes are identified by string ids.
- Nodes use the schema: {"id", "text", "speaker", "type"} where type is
  typically "line" or "choice".
- Edges are exported as {"from", "to", "text"}. The Edge class uses the more
  Python-friendly attribute names: source/target.
- "End" is treated as an optional *implicit* terminal node:
    * Edges may target "End" even if no Node("End") was added.
    * By default, to_dict()/to_json() do NOT inject an explicit "End" node.

This module intentionally avoids embedding task-instance values (e.g., fixed
speaker names) so it can be reused across scripts.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable


IMPLICIT_END_ID = "End"
_VALID_NODE_TYPES = {"line", "choice"}


def _as_str(value: Any) -> str:
    """Convert None/other primitives to a safe string."""

    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _stable_color(key: str, palette: list[str]) -> str:
    """Pick a stable color for a string key.

    Uses md5 to avoid Python's randomized hash().
    """

    if not key:
        return "white"
    digest = hashlib.md5(key.encode("utf-8")).digest()
    idx = digest[0] % len(palette)
    return palette[idx]


def _dot_escape(text: str) -> str:
    """Escape a label string for DOT."""

    # DOT strings use C-like escaping.
    return (
        text.replace("\\", "\\\\")
        .replace("\"", "\\\"")
        .replace("\n", "\\n")
        .replace("\r", "")
    )


@dataclass
class Node:
    id: str
    text: str = ""
    speaker: str = ""
    type: str = "line"  # 'line' | 'choice'

    def __post_init__(self) -> None:
        self.id = _as_str(self.id)
        self.text = _as_str(self.text)
        self.speaker = _as_str(self.speaker)
        self.type = _as_str(self.type) or "line"

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "text": self.text, "speaker": self.speaker, "type": self.type}


@dataclass
class Edge:
    source: str
    target: str
    text: str = ""

    def __post_init__(self) -> None:
        self.source = _as_str(self.source)
        self.target = _as_str(self.target)
        # Export format expects a string; treat None as empty.
        self.text = _as_str(self.text)

    def to_dict(self) -> dict[str, Any]:
        # Keep the engine-facing schema keys.
        return {"from": self.source, "to": self.target, "text": self.text}


class Graph:
    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []
        self._start_id: str | None = None

    # -------------------------
    # Mutation helpers
    # -------------------------

    def add_node(self, node: Node) -> None:
        if not node.id:
            raise ValueError("Node id must be a non-empty string")
        if node.id in self.nodes:
            raise ValueError(f"Node {node.id} already exists")
        self.nodes[node.id] = node
        if self._start_id is None:
            self._start_id = node.id

    def add_edge(self, edge: Edge) -> None:
        self.edges.append(edge)

    # -------------------------
    # Core properties
    # -------------------------

    @property
    def start_id(self) -> str | None:
        """Return the configured start node id.

        If not explicitly set, this returns the first node added (in insertion
        order), which matches the common "first node" constraint.
        """

        if self._start_id is not None:
            return self._start_id
        return next(iter(self.nodes), None)

    @start_id.setter
    def start_id(self, value: str | None) -> None:
        self._start_id = value

    # -------------------------
    # Validation
    # -------------------------

    def validate(self) -> list[str]:
        """Validate structural integrity.

        Checks:
        - All edge sources exist.
        - All edge targets exist, except the implicit terminal "End".
        - All nodes are reachable from the first node (start_id).
        - Node types are within {"line", "choice"} (reported as warnings).
        """

        errors: list[str] = []

        if not self.nodes:
            return ["Graph has no nodes"]

        start = self.start_id
        if start is None or start not in self.nodes:
            return ["Graph start node is missing"]

        # Node type sanity (keep as errors to match strict validators).
        for node_id, node in self.nodes.items():
            if node.type and node.type not in _VALID_NODE_TYPES:
                errors.append(
                    f"Node '{node_id}' has invalid type '{node.type}' (expected one of: {sorted(_VALID_NODE_TYPES)})"
                )

        # Edge endpoint checks.
        for edge in self.edges:
            if edge.source not in self.nodes:
                errors.append(
                    f"Edge '{edge.source}'->'{edge.target}' points from missing node '{edge.source}'"
                )
            if edge.source == IMPLICIT_END_ID:
                errors.append(
                    f"Edge '{edge.source}'->'{edge.target}' leaves terminal node '{IMPLICIT_END_ID}'"
                )

            # Target may be implicit End.
            if edge.target not in self.nodes and edge.target != IMPLICIT_END_ID:
                errors.append(
                    f"Edge '{edge.source}'->'{edge.target}' points to missing node '{edge.target}'"
                )

        # Reachability: consider only edges to existing nodes.
        reachable = self._reachable_from(start)
        for node_id in self.nodes:
            if node_id not in reachable:
                errors.append(
                    f"Unreachable node '{node_id}' (not reachable from start node '{start}')"
                )

        return errors

    def _reachable_from(self, start: str) -> set[str]:
        adj: dict[str, list[str]] = {}
        for e in self.edges:
            if e.source not in adj:
                adj[e.source] = []
            # Only traverse into nodes that exist; implicit End is terminal.
            if e.target in self.nodes:
                adj[e.source].append(e.target)

        seen: set[str] = set()
        stack = [start]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            for nxt in adj.get(cur, []):
                if nxt not in seen:
                    stack.append(nxt)
        return seen

    # -------------------------
    # Export
    # -------------------------

    def to_dict(self, *, include_end: bool = False) -> dict[str, Any]:
        """Serialize to a plain dict.

        Args:
            include_end: If True, include an explicit Node("End") when it is
                referenced by edges but not present.
        """

        nodes: list[Node] = list(self.nodes.values())
        if include_end and IMPLICIT_END_ID not in self.nodes:
            if any(e.target == IMPLICIT_END_ID for e in self.edges):
                nodes = nodes + [Node(id=IMPLICIT_END_ID, type="line", text="", speaker="")]

        return {"nodes": [n.to_dict() for n in nodes], "edges": [e.to_dict() for e in self.edges]}

    def to_json(self, *, include_end: bool = False) -> str:
        return json.dumps(self.to_dict(include_end=include_end), indent=2, ensure_ascii=False)

    # -------------------------
    # DOT export / visualization
    # -------------------------

    def to_dot(self) -> str:
        """Return a Graphviz DOT representation.

        This does not require the graphviz Python package or Graphviz binaries.
        """

        # A small, readable palette.
        palette = [
            "lightyellow",
            "lightcyan",
            "peachpuff",
            "lightpink",
            "lightgreen",
            "thistle",
            "lavender",
        ]

        lines: list[str] = []
        lines.append('digraph "Dialogue Graph" {')
        lines.append('  rankdir="TB";')
        lines.append('  node [fontname="Arial", fontsize="10"];')
        lines.append('  edge [fontname="Arial", fontsize="8"];')

        # Nodes
        for node_id, node in self.nodes.items():
            if node.type == "choice":
                lines.append(
                    f'  "{_dot_escape(node_id)}" [label="{_dot_escape(node_id)}", shape="diamond", style="filled", fillcolor="lightblue"];'
                )
                continue

            label_parts: list[str] = [node_id]
            if node.speaker and node.text:
                label_parts.append(f"{node.speaker}: {node.text}")
            elif node.speaker:
                label_parts.append(node.speaker)
            elif node.text:
                label_parts.append(node.text)

            label = "\\n".join(label_parts)
            fill = _stable_color(node.speaker, palette)
            lines.append(
                f'  "{_dot_escape(node_id)}" [label="{_dot_escape(label)}", shape="box", style="filled,rounded", fillcolor="{fill}"];'
            )

        # Optional implicit End node
        if any(e.target == IMPLICIT_END_ID for e in self.edges) and IMPLICIT_END_ID not in self.nodes:
            lines.append(
                f'  "{IMPLICIT_END_ID}" [label="END", shape="doublecircle", style="filled", fillcolor="lightgray"];'
            )

        # Edges
        for edge in self.edges:
            attrs: list[str] = []
            if edge.text:
                attrs.append(f'label="{_dot_escape(edge.text)}"')
                if "[" in edge.text and "]" in edge.text:
                    attrs.append('color="darkblue"')
                    attrs.append('fontcolor="darkblue"')
                    attrs.append('style="bold"')
                else:
                    attrs.append('color="gray40"')
                    attrs.append('fontcolor="gray40"')
            else:
                attrs.append('color="black"')

            attr_str = "" if not attrs else " [" + ", ".join(attrs) + "]"
            lines.append(
                f'  "{_dot_escape(edge.source)}" -> "{_dot_escape(edge.target)}"{attr_str};'
            )

        lines.append("}")
        return "\n".join(lines) + "\n"

    def write_dot(self, filepath: str) -> str:
        """Write DOT text to a file and return the path."""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.to_dot())
        return filepath

    def visualize(self, output_file: str = "dialogue_graph", format: str = "png") -> str:
        """Render the dialogue graph.

        - If format == "dot", this writes a DOT file (no dependencies).
        - Otherwise, this uses the optional graphviz package + Graphviz binary.

        Args:
            output_file: Output filename (without extension for image formats).
            format: 'png', 'svg', 'pdf', or 'dot'

        Returns:
            Path to the generated file.
        """

        if format == "dot":
            dot_path = output_file if output_file.endswith(".dot") else output_file + ".dot"
            return self.write_dot(dot_path)

        try:
            from graphviz import Digraph
        except ImportError as exc:
            raise ImportError(
                "graphviz package required for image rendering. Install with: pip install graphviz "
                "(or use format='dot' to export without dependencies)."
            ) from exc

        # Build graphviz Digraph using the same styling as to_dot().
        dot = Digraph(comment="Dialogue Graph", format=format)
        dot.attr(rankdir="TB", splines="ortho", nodesep="0.5", ranksep="0.8")
        dot.attr("node", fontname="Arial", fontsize="10")
        dot.attr("edge", fontname="Arial", fontsize="8")

        palette = [
            "lightyellow",
            "lightcyan",
            "peachpuff",
            "lightpink",
            "lightgreen",
            "thistle",
            "lavender",
        ]

        for node_id, node in self.nodes.items():
            if node.type == "choice":
                dot.node(node_id, node_id, shape="diamond", style="filled", fillcolor="lightblue", width="1.5")
                continue

            label_parts: list[str] = [node_id]
            if node.speaker and node.text:
                label_parts.append(f"{node.speaker}: {node.text}")
            elif node.speaker:
                label_parts.append(node.speaker)
            elif node.text:
                label_parts.append(node.text)

            label = "\n".join(label_parts)
            fill = _stable_color(node.speaker, palette)
            dot.node(node_id, label, shape="box", style="filled,rounded", fillcolor=fill, width="2")

        if any(e.target == IMPLICIT_END_ID for e in self.edges):
            dot.node(IMPLICIT_END_ID, "END", shape="doublecircle", style="filled", fillcolor="lightgray", width="0.8")

        for edge in self.edges:
            if edge.text:
                if "[" in edge.text and "]" in edge.text:
                    dot.edge(edge.source, edge.target, label=edge.text, color="darkblue", fontcolor="darkblue", style="bold")
                else:
                    dot.edge(edge.source, edge.target, label=edge.text, color="gray40", fontcolor="gray40")
            else:
                dot.edge(edge.source, edge.target, color="black")

        return dot.render(output_file, cleanup=True)

    # -------------------------
    # Loading helpers
    # -------------------------

    @staticmethod
    def from_json(json_str: str) -> "Graph":
        data = json.loads(json_str)
        return Graph.from_dict(data)

    @staticmethod
    def from_dict(data: dict) -> "Graph":
        graph = Graph()

        for n in data.get("nodes", []):
            graph.add_node(
                Node(
                    id=n.get("id", ""),
                    text=n.get("text", ""),
                    speaker=n.get("speaker", ""),
                    type=n.get("type", "line"),
                )
            )

        for e in data.get("edges", []):
            graph.add_edge(
                Edge(
                    source=e.get("from", ""),
                    target=e.get("to", ""),
                    text=e.get("text", ""),
                )
            )

        return graph

    @staticmethod
    def from_file(filepath: str) -> "Graph":
        with open(filepath, encoding="utf-8") as f:
            return Graph.from_json(f.read())
