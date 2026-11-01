import json
from collections import deque
from typing import Any


class Node:
    def __init__(self, id: str, text: str = "", speaker: str = "", type: str = "line"):
        self.id = id
        self.text = text
        self.speaker = speaker
        self.type = type  # 'line', 'choice'

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "speaker": self.speaker,
            "type": self.type,
        }

    def _attrs(self) -> tuple:
        return (self.id, self.text, self.speaker, self.type)


class Edge:
    def __init__(self, source: str, target: str, text: str = ""):
        self.source = source
        self.target = target
        self.text = text

    def to_dict(self) -> dict[str, Any]:
        d = {"from": self.source, "to": self.target}
        if self.text is not None:
            d["text"] = self.text
        return d


class Graph:
    def __init__(self):
        # Preserve insertion order so the first-added node is the root.
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []

    def add_node(self, node: Node):
        """Register a node.

        Idempotent for identical re-registrations: calling `add_node` twice
        with the same id and attributes is a no-op. Re-adding the same id
        with different attributes still raises `ValueError` to surface bugs.
        """
        existing = self.nodes.get(node.id)
        if existing is not None:
            if existing._attrs() == node._attrs():
                return  # idempotent
            raise ValueError(f"Node {node.id} already exists with different attributes")
        self.nodes[node.id] = node

    def ensure_node(self, node: Node):
        """Idempotent node registration that never raises on duplicates.

        If a node with the same id already exists, this is a no-op (the
        existing node is preserved). Useful for convergence targets like
        `End` that may be registered from multiple code paths.
        """
        if node.id not in self.nodes:
            self.nodes[node.id] = node

    def add_edge(self, edge: Edge):
        self.edges.append(edge)

    def _root_id(self) -> str | None:
        return next(iter(self.nodes), None)

    def validate(self) -> list[str]:
        """Validate the graph structure.

        Checks:
          1. Every edge source resolves to a node.
          2. Every edge target resolves to a node (including `End`, which
             must be a registered node — not just an edge target).
          3. All nodes are reachable from the first-declared (root) node.
        """
        errors: list[str] = []

        for edge in self.edges:
            if edge.source not in self.nodes:
                errors.append(f"Edge source '{edge.source}' not found")
            if edge.target not in self.nodes:
                errors.append(
                    f"Edge '{edge.source}'->'{edge.target}' points to missing node '{edge.target}'"
                )

        # Reachability from root
        root = self._root_id()
        if root is not None:
            adj: dict[str, list[str]] = {nid: [] for nid in self.nodes}
            for e in self.edges:
                if e.source in adj and e.target in self.nodes:
                    adj[e.source].append(e.target)

            seen = {root}
            q = deque([root])
            while q:
                cur = q.popleft()
                for nxt in adj.get(cur, ()):
                    if nxt not in seen:
                        seen.add(nxt)
                        q.append(nxt)

            for nid in self.nodes:
                if nid not in seen:
                    errors.append(f"Node '{nid}' is not reachable from root '{root}'")

        return errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @staticmethod
    def _dot_escape(s: str) -> str:
        if s is None:
            return ""
        return (
            s.replace("\\", "\\\\")
             .replace('"', '\\"')
             .replace("\n", "\\n")
        )

    def to_dot(self) -> str:
        """Return a Graphviz DOT representation of the graph.

        Shape conventions:
          - `shape=box`          for type=="line" nodes
          - `shape=diamond`      for type=="choice" nodes
          - `shape=doublecircle` for the `End` node

        Labels are escaped (backslash, quote, newline). The `End` node, if
        present, is always declared explicitly so Graphviz renders it even
        when it only appears as an edge target.
        """
        esc = self._dot_escape
        lines = ["digraph Dialogue {", "  rankdir=LR;"]

        for node in self.nodes.values():
            if node.id == "End":
                shape = "doublecircle"
            elif node.type == "choice":
                shape = "diamond"
            else:
                shape = "box"

            label_parts = [node.id]
            if node.speaker:
                label_parts.append(f"{node.speaker}: {node.text}" if node.text else node.speaker)
            elif node.text:
                label_parts.append(node.text)
            label = esc("\n".join(label_parts))
            lines.append(f'  "{esc(node.id)}" [label="{label}", shape={shape}];')

        for e in self.edges:
            lines.append(
                f'  "{esc(e.source)}" -> "{esc(e.target)}" [label="{esc(e.text or "")}"];'
            )

        lines.append("}")
        return "\n".join(lines)

    def visualize(self, output_file: str = 'dialogue_graph', format: str = 'png') -> str:
        """
        Create a visual representation of the dialogue graph using graphviz.

        Args:
            output_file: Output filename (without extension)
            format: Output format ('png', 'svg', 'pdf')

        Returns:
            Path to the generated file

        Requires:
            pip install graphviz
            Also requires Graphviz system binary: https://graphviz.org/download/

        Note:
            This renders a bitmap/vector image with `cleanup=True`, which
            deletes the intermediate `.dot` file. If you need a persistent
            `.dot` artifact (e.g., for grading), use `to_dot()` and write it
            yourself. Only nodes present in `self.nodes` are rendered;
            register `End` explicitly if your graph uses it.
        """
        try:
            from graphviz import Digraph
        except ImportError as exc:
            raise ImportError(
                "graphviz package required. Install with: pip install graphviz"
            ) from exc

        dot = Digraph(comment='Dialogue Graph', format=format)
        dot.attr(rankdir='TB', splines='ortho', nodesep='0.5', ranksep='0.8')
        dot.attr('node', fontname='Arial', fontsize='10')
        dot.attr('edge', fontname='Arial', fontsize='8')

        # Speaker color mapping
        colors = {
            'Narrator': 'lightyellow',
            'Guard': 'lightcoral',
            'Stranger': 'plum',
            'Merchant': 'lightgreen',
            'Barkeep': 'peachpuff',
            'Kira': 'lightcyan',
        }

        # Add nodes (iterate over registered nodes only; End must be
        # registered by the caller to appear in output).
        for node_id, node in self.nodes.items():
            text = node.text[:37] + '...' if len(node.text) > 40 else node.text

            if node_id == 'End':
                dot.node('End', 'END', shape='doublecircle', style='filled',
                         fillcolor='lightgray', width='0.8')
                continue

            if node.type == 'choice':
                dot.node(node_id, node_id, shape='diamond', style='filled',
                        fillcolor='lightblue', width='1.5')
            else:
                if node.speaker and text:
                    label = f"{node_id}\\n{node.speaker}: {text}"
                elif node.speaker:
                    label = f"{node_id}\\n{node.speaker}"
                else:
                    label = node_id

                color = colors.get(node.speaker, 'white')
                dot.node(node_id, label, shape='box', style='filled,rounded',
                        fillcolor=color, width='2')

        # Add edges
        for edge in self.edges:
            edge_text = edge.text[:27] + '...' if len(edge.text) > 30 else edge.text

            if edge_text:
                if '[' in edge_text and ']' in edge_text:
                    # Skill check edge
                    dot.edge(edge.source, edge.target, label=edge_text,
                            color='darkblue', fontcolor='darkblue', style='bold')
                else:
                    dot.edge(edge.source, edge.target, label=edge_text,
                            color='gray40', fontcolor='gray40')
            else:
                dot.edge(edge.source, edge.target, color='black')

        # Render
        output_path = dot.render(output_file, cleanup=True)
        return output_path

    @staticmethod
    def from_json(json_str: str) -> 'Graph':
        """Load a Graph from JSON string."""
        data = json.loads(json_str)
        return Graph.from_dict(data)

    @staticmethod
    def from_dict(data: dict) -> 'Graph':
        """Load a Graph from a dictionary."""
        graph = Graph()
        for n in data.get('nodes', []):
            graph.nodes[n['id']] = Node(
                id=n['id'],
                text=n.get('text', ''),
                speaker=n.get('speaker', ''),
                type=n.get('type', 'line'),
            )
        for e in data.get('edges', []):
            graph.edges.append(Edge(
                source=e['from'],
                target=e['to'],
                text=e.get('text', ''),
            ))
        return graph

    @staticmethod
    def from_file(filepath: str) -> 'Graph':
        """Load a Graph from a JSON file."""
        with open(filepath, encoding='utf-8') as f:
            return Graph.from_json(f.read())
