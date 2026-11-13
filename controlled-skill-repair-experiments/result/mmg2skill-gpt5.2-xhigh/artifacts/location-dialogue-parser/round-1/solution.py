import json
import re
from collections import deque
from pathlib import Path
from typing import Dict, List, Tuple


_SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")
_CHOICE_RE = re.compile(r"^\s*(\d+)\.\s*(.+?)\s*->\s*(\S+)\s*$")
_LINE_RE = re.compile(r"^\s*([^:]+?)\s*:\s*(.+?)\s*->\s*(\S+)\s*$")


def _split_sections(text: str) -> List[Tuple[str, List[str]]]:
    sections: List[Tuple[str, List[str]]] = []
    current_id: str | None = None
    current_lines: List[str] = []

    for raw_line in text.splitlines():
        m = _SECTION_RE.match(raw_line)
        if m:
            if current_id is not None:
                sections.append((current_id, current_lines))
            current_id = m.group(1).strip()
            current_lines = []
            continue

        if current_id is None:
            # Ignore any preamble before the first [Section].
            continue

        current_lines.append(raw_line.rstrip("\n"))

    if current_id is not None:
        sections.append((current_id, current_lines))

    return sections


def parse_script(text: str) -> Dict[str, List[Dict[str, str]]]:
    """Parse a dialogue script into a JSON-serializable graph.

    Returns:
        {"nodes": [...], "edges": [...]} where nodes are:
          {"id","text","speaker","type"} and edges are {"from","to","text"}.
    """

    sections = _split_sections(text)
    if not sections:
        return {"nodes": [], "edges": []}

    nodes: List[Dict[str, str]] = []
    edges: List[Dict[str, str]] = []

    for node_id, raw_lines in sections:
        content_lines = [ln.strip() for ln in raw_lines if ln.strip()]
        if not content_lines:
            raise ValueError(f"Section [{node_id}] is empty")

        # Choice node: all non-empty lines are numbered options.
        choice_matches = [_CHOICE_RE.match(ln) for ln in content_lines]
        if all(m is not None for m in choice_matches):
            nodes.append({"id": node_id, "text": "", "speaker": "", "type": "choice"})
            for m in choice_matches:
                assert m is not None
                option_body = m.group(2).strip()
                target = m.group(3).strip()
                edges.append({"from": node_id, "to": target, "text": option_body})
            continue

        # Line node: exactly one line with Speaker: ... -> Target
        if len(content_lines) != 1:
            raise ValueError(
                f"Section [{node_id}] must be either all choices or a single line; "
                f"got {len(content_lines)} non-empty lines"
            )

        m = _LINE_RE.match(content_lines[0])
        if not m:
            raise ValueError(f"Unrecognized line format in [{node_id}]: {content_lines[0]!r}")

        speaker = m.group(1).strip()
        line_text = m.group(2).strip()
        target = m.group(3).strip()

        nodes.append({"id": node_id, "text": line_text, "speaker": speaker, "type": "line"})
        edges.append({"from": node_id, "to": target, "text": ""})

    graph: Dict[str, List[Dict[str, str]]] = {"nodes": nodes, "edges": edges}

    # Enforce reachability constraint by pruning unreachable nodes.
    graph = _prune_unreachable(graph)

    errors = validate_graph(graph)
    if errors:
        raise ValueError("Graph validation failed:\n" + "\n".join(errors))

    return graph


def validate_graph(graph: Dict[str, List[Dict[str, str]]]) -> List[str]:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    errors: List[str] = []
    node_ids = [n.get("id") for n in nodes]

    if not node_ids:
        return errors

    node_id_set = set(node_ids)

    for e in edges:
        src = e.get("from")
        dst = e.get("to")
        if src not in node_id_set:
            errors.append(f"Edge has unknown source: {src!r}")
        if dst != "End" and dst not in node_id_set:
            errors.append(f"Edge from {src!r} targets missing node: {dst!r}")

    # Reachability check (excluding terminal End).
    reachable = _reachable_nodes(nodes, edges)
    unreachable = [nid for nid in node_ids if nid not in reachable]
    if unreachable:
        errors.append("Unreachable nodes: " + ", ".join(unreachable))

    return errors


def _reachable_nodes(
    nodes: List[Dict[str, str]], edges: List[Dict[str, str]]
) -> set[str]:
    if not nodes:
        return set()

    start = nodes[0]["id"]
    adj: Dict[str, List[str]] = {}
    for e in edges:
        src = e["from"]
        dst = e["to"]
        if dst == "End":
            continue
        adj.setdefault(src, []).append(dst)

    seen: set[str] = set()
    q: deque[str] = deque([start])
    while q:
        cur = q.popleft()
        if cur in seen:
            continue
        seen.add(cur)
        for nxt in adj.get(cur, []):
            if nxt not in seen:
                q.append(nxt)
    return seen


def _prune_unreachable(graph: Dict[str, List[Dict[str, str]]]) -> Dict[str, List[Dict[str, str]]]:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    if not nodes:
        return graph

    reachable = _reachable_nodes(nodes, edges)
    nodes_pruned = [n for n in nodes if n.get("id") in reachable]
    reachable_set = {n["id"] for n in nodes_pruned}

    edges_pruned = [
        e
        for e in edges
        if e.get("from") in reachable_set
        and (e.get("to") == "End" or e.get("to") in reachable_set)
    ]

    return {"nodes": nodes_pruned, "edges": edges_pruned}


def graph_to_dot(graph: Dict[str, List[Dict[str, str]]]) -> str:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    def q(s: str) -> str:
        # json.dumps gives us a properly quoted/escaped string.
        return json.dumps(s, ensure_ascii=False)

    lines: List[str] = [
        "digraph Dialogue {",
        "  rankdir=LR;",
        "  node [fontname=\"Helvetica\"];",
    ]

    # Add an explicit End terminal if referenced.
    if any(e.get("to") == "End" for e in edges):
        lines.append(f"  {q('End')} [shape=doublecircle];")

    for n in nodes:
        nid = n.get("id", "")
        ntype = n.get("type", "line")
        speaker = n.get("speaker", "")
        text = n.get("text", "")

        if ntype == "choice":
            shape = "diamond"
            label = nid
        else:
            shape = "box"
            label = nid if not (speaker or text) else f"{nid}\\n{speaker}: {text}"

        lines.append(f"  {q(nid)} [shape={shape}, label={q(label)}];")

    for e in edges:
        src = e.get("from", "")
        dst = e.get("to", "")
        label = e.get("text", "")
        if label:
            lines.append(f"  {q(src)} -> {q(dst)} [label={q(label)}];")
        else:
            lines.append(f"  {q(src)} -> {q(dst)};")

    lines.append("}")
    return "\n".join(lines) + "\n"


def main() -> None:
    script_path = Path("/app/script.txt")
    out_json = Path("/app/dialogue.json")
    out_dot = Path("/app/dialogue.dot")

    text = script_path.read_text(encoding="utf-8")
    graph = parse_script(text)

    out_json.write_text(json.dumps(graph, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out_dot.write_text(graph_to_dot(graph), encoding="utf-8")


if __name__ == "__main__":
    main()
