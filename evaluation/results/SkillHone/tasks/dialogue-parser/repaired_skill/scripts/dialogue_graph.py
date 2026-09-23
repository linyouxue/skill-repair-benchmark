import json
from typing import Any


class Node:
    def __init__(self, id: str, text: str = "", speaker: str = "", type: str = "line"):
        self.id = id
        self.text = text
        self.speaker = speaker
        self.type = type # 'line', 'choice'

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "speaker": self.speaker,
            "type": self.type
        }

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
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []

    def to_dot(self) -> str:
        """Export the graph as Graphviz DOT source text.

        This does not require the external `graphviz` Python package nor the Graphviz
        system binary; it simply returns a `.dot` string.
        """
        def esc(s: str) -> str:
            return (s or "").replace("\\", "\\\\").replace('"', '\\"')

        lines: list[str] = ["digraph Dialogue {", "  rankdir=TB;"]

        # Nodes
        for node_id, node in self.nodes.items():
            if node.type == "choice":
                label = node_id
                attrs = "shape=diamond, style=filled, fillcolor=lightblue"
            else:
                if node.speaker and node.text:
                    label = f"{node_id}\\n{node.speaker}: {node.text}"
                elif node.speaker:
                    label = f"{node_id}\\n{node.speaker}"
                else:
                    label = node_id
                attrs = "shape=box, style=\"filled,rounded\", fillcolor=white"

            lines.append(f'  "{esc(node_id)}" [label="{esc(label)}", {attrs}];')

        # If edges reference End, include an explicit End node in DOT.
        if any(e.target == "End" for e in self.edges):
            lines.append('  "End" [label="END", shape=doublecircle, style=filled, fillcolor=lightgray];')

        # Edges
        for e in self.edges:
            if e.text:
                lines.append(f'  "{esc(e.source)}" -> "{esc(e.target)}" [label="{esc(e.text)}"];')
            else:
                lines.append(f'  "{esc(e.source)}" -> "{esc(e.target)}";')

        lines.append("}")
        return "\n".join(lines)

    def validate(self) -> list[str]:
        """Validate the graph structure.

        Checks:
          - edge endpoints exist (target may be the terminal "End")
          - all nodes are reachable from the first inserted node
        """
        errors = []

        for edge in self.edges:
            if edge.source not in self.nodes:
                errors.append(f"Edge source '{edge.source}' not found")
            if edge.target not in self.nodes and edge.target != "End":
                errors.append(f"Edge target '{edge.target}' not found")

        # Reachability from first node (in insertion order)
        if self.nodes:
            start = next(iter(self.nodes.keys()))
            adj: dict[str, list[str]] = {nid: [] for nid in self.nodes}
            for edge in self.edges:
                if edge.source in adj:
                    adj[edge.source].append(edge.target)

            seen = set([start])
            stack = [start]
            while stack:
                cur = stack.pop()
                for nxt in adj.get(cur, []):
                    if nxt == "End":
                        continue
                    if nxt in self.nodes and nxt not in seen:
                        seen.add(nxt)
                        stack.append(nxt)

            unreachable = [nid for nid in self.nodes.keys() if nid not in seen]
            if unreachable:
                errors.append(f"Unreachable nodes from '{start}': {', '.join(unreachable)}")

        return errors

    def add_node(self, node: Node):
        if node.id in self.nodes:
            raise ValueError(f"Node {node.id} already exists")
        self.nodes[node.id] = node

    def add_edge(self, edge: Edge):
        self.edges.append(edge)

    # validate() moved above to include reachability + dot support

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges]
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

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

        # Add nodes
        for node_id, node in self.nodes.items():
            text = node.text[:37] + '...' if len(node.text) > 40 else node.text

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

        # Add End node
        dot.node('End', 'END', shape='doublecircle', style='filled',
                fillcolor='lightgray', width='0.8')

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
                type=n.get('type', 'line')
            )
        for e in data.get('edges', []):
            graph.edges.append(Edge(
                source=e['from'],
                target=e['to'],
                text=e.get('text', '')
            ))
        return graph

    @staticmethod
    def from_file(filepath: str) -> 'Graph':
        """Load a Graph from a JSON file."""
        with open(filepath, encoding='utf-8') as f:
            return Graph.from_json(f.read())
