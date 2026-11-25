import json
from collections import deque
from typing import Any, Optional


class Node:
    def __init__(self, id: str, text: str = "", speaker: str = "", type: str = "line"):
        self.id = id
        self.text = text
        self.speaker = speaker
        self.type = type  # 'line', 'choice'

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "text": self.text, "speaker": self.speaker, "type": self.type}


class Edge:
    def __init__(self, source: str, target: str, text: str = ""):
        self.source = source
        self.target = target
        self.text = text

    def to_dict(self) -> dict[str, Any]:
        # Keep schema stable: always include text
        return {"from": self.source, "to": self.target, "text": self.text if self.text is not None else ""}


class Graph:
    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []

    def add_node(self, node: Node):
        if node.id in self.nodes:
            raise ValueError(f"Node {node.id} already exists")
        self.nodes[node.id] = node

    def upsert_node(self, node: Node) -> None:
        """Insert or update a node.

        This supports the common parsing pattern of creating placeholder nodes when
        an edge references a target before its section is parsed, then upgrading
        the placeholder later.
        """
        self.nodes[node.id] = node

    def add_edge(self, edge: Edge):
        self.edges.append(edge)

    def validate(self) -> list[str]:
        """Validate the graph structure.

        Notes:
        - All edge sources and targets must exist as nodes, including 'End' if referenced.
        - This method does not enforce reachability; parsers/tasks may enforce that separately.
        """
        errors: list[str] = []
        for edge in self.edges:
            if edge.source not in self.nodes:
                errors.append(f"Edge source '{edge.source}' not found")
            if edge.target not in self.nodes:
                if edge.target == "End":
                    errors.append(
                        "Edge target 'End' not found (if you reference 'End', you must add Node(id='End', ...) to the graph)"
                    )
                else:
                    errors.append(f"Edge target '{edge.target}' not found")
        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @staticmethod
    def _dot_escape(value: str) -> str:
        # DOT labels use C-like escaping; minimally escape backslashes, quotes and newlines.
        return (
            value.replace("\\", "\\\\")
            .replace('"', "\\\"")
            .replace("\r\n", "\\n")
            .replace("\n", "\\n")
            .replace("\r", "\\n")
        )

    def to_dot(self) -> str:
        """Export the graph as Graphviz DOT source.

        Works without graphviz installed.
        """
        lines: list[str] = []
        lines.append("digraph Dialogue {")
        lines.append("  rankdir=TB;")
        lines.append("  splines=ortho;")
        lines.append("  nodesep=0.5;")
        lines.append("  ranksep=0.8;")
        lines.append("  node [fontname=\"Arial\", fontsize=10];")
        lines.append("  edge [fontname=\"Arial\", fontsize=8];")

        # Speaker color mapping (kept consistent with visualize())
        colors = {
            "Narrator": "lightyellow",
            "Guard": "lightcoral",
            "Stranger": "plum",
            "Merchant": "lightgreen",
            "Barkeep": "peachpuff",
            "Kira": "lightcyan",
        }

        # Nodes
        for node_id, node in self.nodes.items():
            if node.type == "choice":
                label = self._dot_escape(node_id)
                lines.append(
                    f"  \"{self._dot_escape(node_id)}\" [label=\"{label}\", shape=diamond, style=filled, fillcolor=lightblue, width=1.5];"
                )
            else:
                text = node.text[:37] + "..." if len(node.text) > 40 else node.text
                if node.speaker and text:
                    label = f"{node_id}\\n{node.speaker}: {text}"
                elif node.speaker:
                    label = f"{node_id}\\n{node.speaker}"
                else:
                    label = node_id
                fill = colors.get(node.speaker, "white")
                lines.append(
                    f"  \"{self._dot_escape(node_id)}\" [label=\"{self._dot_escape(label)}\", shape=box, style=\"filled,rounded\", fillcolor=\"{fill}\", width=2];"
                )

        # Edges
        for edge in self.edges:
            edge_text = edge.text[:27] + "..." if edge.text and len(edge.text) > 30 else (edge.text or "")
            attrs: list[str] = []
            if edge_text:
                attrs.append(f"label=\"{self._dot_escape(edge_text)}\"")
                if "[" in edge_text and "]" in edge_text:
                    attrs.append("color=darkblue")
                    attrs.append("fontcolor=darkblue")
                    attrs.append("style=bold")
                else:
                    attrs.append("color=gray40")
                    attrs.append("fontcolor=gray40")
            else:
                attrs.append("color=black")

            attr_str = ", ".join(attrs)
            lines.append(
                f"  \"{self._dot_escape(edge.source)}\" -> \"{self._dot_escape(edge.target)}\" [{attr_str}];"
            )

        lines.append("}")
        return "\n".join(lines) + "\n"

    def write_dot(self, path: str) -> None:
        """Write DOT source to a file."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_dot())

    def visualize(self, output_file: str = "dialogue_graph", format: str = "png") -> str:
        """Create a visual representation of the dialogue graph using graphviz.

        This renders the same structure as `to_dot()` (visualize reflects the graph; it does
        not inject extra nodes like 'End').

        Args:
            output_file: Output filename (without extension)
            format: Output format ('png', 'svg', 'pdf')

        Returns:
            Path to the generated file

        Requires:
            pip install graphviz
            Also requires Graphviz system binary: https://graphviz.org/download/
        """
        try:
            from graphviz import Source
        except ImportError as exc:
            raise ImportError("graphviz package required. Install with: pip install graphviz") from exc

        src = Source(self.to_dot(), format=format)
        # graphviz.Source.render returns the output path
        return src.render(filename=output_file, cleanup=True)

    @staticmethod
    def from_json(json_str: str) -> "Graph":
        """Load a Graph from JSON string."""
        data = json.loads(json_str)
        return Graph.from_dict(data)

    @staticmethod
    def from_dict(data: dict) -> "Graph":
        """Load a Graph from a dictionary."""
        graph = Graph()
        for n in data.get("nodes", []):
            graph.nodes[n["id"]] = Node(
                id=n["id"],
                text=n.get("text", ""),
                speaker=n.get("speaker", ""),
                type=n.get("type", "line"),
            )
        for e in data.get("edges", []):
            graph.edges.append(Edge(source=e["from"], target=e["to"], text=e.get("text", "")))
        return graph

    @staticmethod
    def from_file(filepath: str) -> "Graph":
        """Load a Graph from a JSON file."""
        with open(filepath, encoding="utf-8") as f:
            return Graph.from_json(f.read())
