"""Dialogue script parser using the Dialogue Graph skill.

This repository is a Skill bundle, but the benchmark issue requires a small,
reusable parser entrypoint:

    def parse_script(text: str) -> dict

The returned dict must have the shape:
    {"nodes": [{"id","text","speaker","type"}], "edges": [{"from","to","text"}]}

The parser supports a simple script format:
  - Section headers: [NodeId]
  - Dialogue lines: Speaker: text -> TargetId
  - Choices: 1. choice text -> TargetId

Notes:
  - Each section becomes at least one node (a "line" node with empty content)
    so it can be targeted and is reachable.
  - A section containing choices also creates an additional "choice" hub node
    with id f"{SectionId}__choice".
  - If a section has both dialogue lines and choices, dialogue lines connect to
    the choice hub, and choices connect onward.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional

from dialogue_graph import Edge, Graph, Node


_SECTION_RE = re.compile(r"^\[(?P<id>[^\]]+)\]\s*$")
_LINE_RE = re.compile(r"^(?P<speaker>[^:]+):\s*(?P<text>.+?)(?:\s*->\s*(?P<to>[A-Za-z0-9_\-]+))?\s*$")
_CHOICE_RE = re.compile(r"^(?P<num>\d+)\.\s*(?P<text>.+?)(?:\s*->\s*(?P<to>[A-Za-z0-9_\-]+))?\s*$")


@dataclass
class _PendingEdge:
    source: str
    target: str
    text: str = ""


def _ensure_node(graph: Graph, node_id: str, *, type: str = "line") -> None:
    if node_id in graph.nodes:
        # Do not overwrite existing node content.
        return
    graph.add_node(Node(id=node_id, type=type))


def parse_script(text: str):
    """Parse dialogue script content into a JSON-serializable graph dict."""

    graph = Graph()
    pending: list[_PendingEdge] = []

    current_section: Optional[str] = None
    section_has_choice: dict[str, bool] = {}
    last_line_node: dict[str, str] = {}

    def section_choice_id(section_id: str) -> str:
        return f"{section_id}__choice"

    # First pass: create nodes and collect edges.
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        m = _SECTION_RE.match(line)
        if m:
            current_section = m.group("id").strip()
            _ensure_node(graph, current_section, type="line")
            section_has_choice.setdefault(current_section, False)
            continue

        if current_section is None:
            # Ignore prelude text before the first section.
            continue

        m = _CHOICE_RE.match(line)
        if m:
            section_has_choice[current_section] = True
            choice_hub = section_choice_id(current_section)
            _ensure_node(graph, choice_hub, type="choice")

            # Ensure the section node leads into the choice hub unless we later
            # connect via a dialogue line.
            pending.append(_PendingEdge(source=current_section, target=choice_hub))

            choice_text = m.group("text").strip()
            to = (m.group("to") or "").strip() or "End"
            pending.append(_PendingEdge(source=choice_hub, target=to, text=choice_text))
            continue

        m = _LINE_RE.match(line)
        if m:
            speaker = m.group("speaker").strip()
            content = m.group("text").strip()
            to = (m.group("to") or "").strip()

            # Create a unique node id for this line.
            idx = 1
            base = f"{current_section}__line"
            node_id = f"{base}{idx}"
            while node_id in graph.nodes:
                idx += 1
                node_id = f"{base}{idx}"

            graph.add_node(Node(id=node_id, speaker=speaker, text=content, type="line"))
            last_line_node[current_section] = node_id

            # Connect section entry to first line (or chain lines).
            prev = current_section
            # If prior line exists and was the last created for this section, chain.
            if idx > 1:
                prev = f"{base}{idx-1}"
            pending.append(_PendingEdge(source=prev, target=node_id))

            if to:
                pending.append(_PendingEdge(source=node_id, target=to))
            else:
                # If no explicit transition, and this section has choices later,
                # connect to its choice hub.
                if section_has_choice.get(current_section):
                    pending.append(_PendingEdge(source=node_id, target=section_choice_id(current_section)))
            continue

        # Unknown line format: ignore.

    # Second pass: ensure all referenced target nodes exist (except End).
    for e in pending:
        if e.target and e.target != "End":
            _ensure_node(graph, e.target, type="line")

    # Add edges (deduplicate trivial duplicates).
    seen = set()
    for e in pending:
        key = (e.source, e.target, e.text)
        if key in seen:
            continue
        seen.add(key)
        graph.add_edge(Edge(source=e.source, target=e.target, text=e.text))

    # If a section has a choice hub, make sure the last dialogue line (if any)
    # flows into it, rather than the empty section node.
    # This is optional, but helps produce more natural graphs.
    for section_id, has_choice in section_has_choice.items():
        if not has_choice:
            continue
        hub = section_choice_id(section_id)
        line_node = last_line_node.get(section_id)
        if line_node:
            # Remove the section->hub edge if present; replace with line->hub.
            graph.edges = [
                ed
                for ed in graph.edges
                if not (ed.source == section_id and ed.target == hub and (ed.text or "") == "")
            ]
            if (line_node, hub, "") not in seen:
                graph.add_edge(Edge(source=line_node, target=hub))

    # Validate and return.
    errors = graph.validate()
    if errors:
        raise ValueError("Invalid dialogue graph: " + "; ".join(errors))

    return graph.to_dict()


def main() -> None:
    """CLI helper: read /app/script.txt and write /app/dialogue.json/.dot."""

    import pathlib

    script_path = pathlib.Path("/app/script.txt")
    out_json = pathlib.Path("/app/dialogue.json")
    out_dot = pathlib.Path("/app/dialogue.dot")

    text = script_path.read_text(encoding="utf-8")
    data = parse_script(text)

    # Re-hydrate to use to_dot() reliably.
    graph = Graph.from_dict(data)

    out_json.write_text(graph.to_json(), encoding="utf-8")
    out_dot.write_text(graph.to_dot(), encoding="utf-8")


if __name__ == "__main__":
    main()
