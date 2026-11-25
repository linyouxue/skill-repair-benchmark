import json
import re
from collections import OrderedDict, deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


_HEADER_RE = re.compile(r"^\[(?P<id>[^\]]+)\]\s*$")
_CHOICE_RE = re.compile(r"^\s*(?P<num>\d+)\.\s*(?P<rest>.+?)\s*$")


@dataclass
class Node:
    id: str
    text: str
    speaker: str
    type: str  # "line" | "choice"


@dataclass
class Edge:
    from_: str
    to: str
    text: str


def _split_arrow(s: str) -> Tuple[str, Optional[str]]:
    """Split a line on the last '->', returning (left, right_or_none)."""
    left, sep, right = s.rpartition("->")
    if not sep:
        return s.strip(), None
    return left.strip(), right.strip() or None


def _escape_dot_label(s: str) -> str:
    return (
        s.replace("\\", "\\\\")
        .replace('"', "\\\"")
        .replace("\n", "\\n")
    )


def parse_script(text: str) -> Dict[str, List[Dict[str, str]]]:
    """Parse a dialogue script into a JSON-serializable graph.

    Returns:
        {"nodes": [{id,text,speaker,type}, ...], "edges": [{from,to,text}, ...]}

    Validation performed:
      1) All nodes reachable from the first declared node.
      2) All edge targets exist (implicit nodes are created for undefined targets).
    """

    lines = text.splitlines()

    # --- Phase 1: split into sections ---
    sections: List[Tuple[str, List[str]]] = []
    current_id: Optional[str] = None
    current_body: List[str] = []

    for raw in lines:
        m = _HEADER_RE.match(raw.strip())
        if m:
            if current_id is not None:
                sections.append((current_id, current_body))
            current_id = m.group("id").strip()
            current_body = []
        else:
            if current_id is None:
                # Ignore any leading junk before the first header.
                continue
            current_body.append(raw.rstrip("\n"))

    if current_id is not None:
        sections.append((current_id, current_body))

    if not sections:
        raise ValueError("No sections found (expected [NodeId] headers).")

    first_node_id = sections[0][0]

    # --- Phase 2: parse sections into nodes/edges ---
    nodes: "OrderedDict[str, Node]" = OrderedDict()
    edges: List[Edge] = []

    def add_node(node: Node) -> None:
        if node.id in nodes:
            # If a node is repeated, keep the first definition.
            return
        nodes[node.id] = node

    def add_edge(src: str, dst: str, label: str) -> None:
        edges.append(Edge(from_=src, to=dst, text=label))

    referenced_targets: List[str] = []

    for section_id, body_lines in sections:
        body = [ln.strip() for ln in body_lines if ln.strip()]

        # Choice node if any numbered options exist.
        is_choice = any(_CHOICE_RE.match(ln) for ln in body)

        if is_choice:
            add_node(Node(id=section_id, text="", speaker="", type="choice"))
            for ln in body:
                cm = _CHOICE_RE.match(ln)
                if not cm:
                    # Non-choice lines inside a choice block are ignored.
                    continue
                option_text_raw = cm.group("rest").strip()
                option_text, target = _split_arrow(option_text_raw)
                if not target:
                    raise ValueError(f"Choice option missing target in [{section_id}]: {ln}")
                add_edge(section_id, target, option_text)
                referenced_targets.append(target)
        else:
            # Treat each non-empty line as a line node, chained if needed.
            if not body:
                add_node(Node(id=section_id, text="", speaker="", type="line"))
                continue

            prev_id: Optional[str] = None
            for i, ln in enumerate(body):
                speaker = ""
                content = ln

                if ":" in ln:
                    maybe_speaker, rest = ln.split(":", 1)
                    if maybe_speaker.strip():
                        speaker = maybe_speaker.strip()
                        content = rest.strip()

                line_text, target = _split_arrow(content)

                node_id = section_id if i == 0 else f"{section_id}#{i+1}"
                add_node(Node(id=node_id, text=line_text, speaker=speaker, type="line"))

                if prev_id is not None:
                    add_edge(prev_id, node_id, "")

                if target:
                    add_edge(node_id, target, "")
                    referenced_targets.append(target)

                prev_id = node_id

    # --- Phase 3: create implicit nodes for forward references ---
    for tgt in referenced_targets:
        if tgt not in nodes:
            add_node(Node(id=tgt, text="", speaker="", type="line"))

    # --- Phase 4: reachability validation ---
    adjacency: Dict[str, List[str]] = {nid: [] for nid in nodes.keys()}
    for e in edges:
        if e.from_ in adjacency:
            adjacency[e.from_].append(e.to)

    reachable = set()
    q = deque([first_node_id])
    while q:
        n = q.popleft()
        if n in reachable:
            continue
        reachable.add(n)
        for nxt in adjacency.get(n, []):
            if nxt not in reachable:
                q.append(nxt)

    unreachable = [nid for nid in nodes.keys() if nid not in reachable]
    if unreachable:
        raise ValueError(
            "Unreachable nodes from first node "
            f"[{first_node_id}]: {', '.join(unreachable)}"
        )

    graph = {
        "nodes": [
            {"id": n.id, "text": n.text, "speaker": n.speaker, "type": n.type}
            for n in nodes.values()
        ],
        "edges": [
            {"from": e.from_, "to": e.to, "text": e.text}
            for e in edges
        ],
    }
    return graph


def graph_to_dot(graph: Dict[str, List[Dict[str, str]]]) -> str:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    node_by_id = {n["id"]: n for n in nodes}

    out: List[str] = []
    out.append("digraph Dialogue {")
    out.append("  rankdir=LR;")
    out.append("  node [fontname=Helvetica];")

    for n in nodes:
        nid = n["id"]
        ntype = n.get("type", "line")
        speaker = n.get("speaker", "")
        text = n.get("text", "")

        if ntype == "choice":
            label = f"{nid}\\n(CHOICE)"
            shape = "diamond"
        else:
            if speaker and text:
                label = f"{nid}\\n{speaker}: {text}"
            elif text:
                label = f"{nid}\\n{text}"
            else:
                label = nid
            shape = "box"

        out.append(
            f"  \"{_escape_dot_label(nid)}\" "
            f"[shape={shape}, label=\"{_escape_dot_label(label)}\"];"
        )

    for e in edges:
        src = e["from"]
        dst = e["to"]
        label = e.get("text", "")
        if src not in node_by_id or dst not in node_by_id:
            continue
        if label:
            out.append(
                f"  \"{_escape_dot_label(src)}\" -> \"{_escape_dot_label(dst)}\" "
                f"[label=\"{_escape_dot_label(label)}\"];"
            )
        else:
            out.append(
                f"  \"{_escape_dot_label(src)}\" -> \"{_escape_dot_label(dst)}\";"
            )

    out.append("}")
    return "\n".join(out) + "\n"


def main() -> None:
    with open("/app/script.txt", "r", encoding="utf-8") as f:
        text = f.read()

    graph = parse_script(text)

    with open("/app/dialogue.json", "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
        f.write("\n")

    dot = graph_to_dot(graph)
    with open("/app/dialogue.dot", "w", encoding="utf-8") as f:
        f.write(dot)


if __name__ == "__main__":
    main()
