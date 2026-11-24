import json
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


_SECTION_RE = re.compile(r"^\[(?P<id>[^\]]+)\]\s*$")
_CHOICE_RE = re.compile(r"^\s*(?:\d+\.|[-*])\s+\S")


@dataclass(frozen=True)
class ParsedNode:
    id: str
    text: str
    speaker: str
    type: str  # 'line' | 'choice'


@dataclass(frozen=True)
class ParsedEdge:
    from_id: str
    to_id: str
    text: str


def _split_transition(line: str) -> Tuple[str, Optional[str]]:
    if "->" not in line:
        return line.strip(), None

    left, right = line.rsplit("->", 1)
    left = left.strip()
    target = right.strip()
    return left, target or None


def _parse_speaker_text(line: str) -> Tuple[str, str]:
    if ":" not in line:
        return "", line.strip()

    speaker, text = line.split(":", 1)
    return speaker.strip(), text.strip()


def parse_script(text: str) -> Dict[str, List[dict]]:
    """Parse a dialogue script into a JSON-serializable graph.

    Returns a dict:
      {"nodes": [{"id","text","speaker","type"}],
       "edges": [{"from","to","text"}]}

    Validation rules enforced:
      1) All nodes must be reachable from the first node.
      2) All edge targets must exist, except sentinel target 'End'.
    """

    lines = [ln.rstrip("\n") for ln in text.splitlines()]

    sections: List[Tuple[str, List[str]]] = []
    current_id: Optional[str] = None
    current_lines: List[str] = []

    def flush() -> None:
        nonlocal current_id, current_lines
        if current_id is None:
            return
        # Keep internal non-empty lines; blank lines separate blocks.
        body = [ln.strip() for ln in current_lines if ln.strip()]
        sections.append((current_id, body))
        current_id = None
        current_lines = []

    for ln in lines:
        m = _SECTION_RE.match(ln.strip())
        if m:
            flush()
            current_id = m.group("id").strip()
            current_lines = []
        else:
            if current_id is not None:
                current_lines.append(ln)

    flush()

    if not sections:
        raise ValueError("No sections found. Expected headers like [Start].")

    nodes: List[ParsedNode] = []
    edges: List[ParsedEdge] = []

    seen_ids: set[str] = set()

    for node_id, body in sections:
        if node_id in seen_ids:
            raise ValueError(f"Duplicate section id: {node_id}")
        seen_ids.add(node_id)

        has_choice_lines = any(_CHOICE_RE.match(ln) for ln in body)
        node_type = "choice" if has_choice_lines else "line"

        if node_type == "line":
            if not body:
                # Empty line node: keep it, no outgoing edges.
                nodes.append(ParsedNode(id=node_id, speaker="", text="", type="line"))
                continue

            # Prefer the first non-empty line as the node content.
            content, target = _split_transition(body[0])
            speaker, text_content = _parse_speaker_text(content)
            nodes.append(ParsedNode(id=node_id, speaker=speaker, text=text_content, type="line"))

            if target is not None:
                edges.append(ParsedEdge(from_id=node_id, to_id=target, text=""))

            # If more lines exist, treat them as additional auto-transitions/content.
            # To keep output simple/deterministic, additional lines only add edges.
            for extra in body[1:]:
                content2, target2 = _split_transition(extra)
                if target2 is None:
                    # Ignore additional plain content for now (rare in provided scripts).
                    continue
                edges.append(ParsedEdge(from_id=node_id, to_id=target2, text=""))

        else:  # choice node
            prompt_speaker = ""
            prompt_text_parts: List[str] = []

            # Non-choice lines become prompt text; choice lines become labeled edges.
            for ln in body:
                if _CHOICE_RE.match(ln):
                    option, target = _split_transition(ln)
                    if not target:
                        raise ValueError(f"Choice missing target in [{node_id}]: {ln}")
                    edges.append(ParsedEdge(from_id=node_id, to_id=target, text=option.strip()))
                else:
                    content, _target = _split_transition(ln)
                    spk, txt = _parse_speaker_text(content)
                    if spk and not prompt_speaker:
                        prompt_speaker = spk
                    if txt:
                        prompt_text_parts.append(txt)

            nodes.append(
                ParsedNode(
                    id=node_id,
                    speaker=prompt_speaker,
                    text=" ".join(prompt_text_parts).strip(),
                    type="choice",
                )
            )

    node_ids = {n.id for n in nodes}

    # Validate edge endpoints (except sentinel 'End')
    for e in edges:
        if e.from_id not in node_ids:
            raise ValueError(f"Edge from missing node: {e.from_id}")
        if e.to_id != "End" and e.to_id not in node_ids:
            raise ValueError(f"Edge '{e.from_id}' -> '{e.to_id}' points to missing node")

    # Reachability from first node
    start_id = nodes[0].id
    adjacency: Dict[str, List[str]] = {}
    for e in edges:
        adjacency.setdefault(e.from_id, []).append(e.to_id)

    reachable: set[str] = set()
    stack: List[str] = [start_id]
    while stack:
        cur = stack.pop()
        if cur in reachable:
            continue
        reachable.add(cur)
        for nxt in adjacency.get(cur, []):
            if nxt == "End":
                continue
            if nxt not in reachable:
                stack.append(nxt)

    unreachable = sorted(node_ids - reachable)
    if unreachable:
        raise ValueError(f"Unreachable nodes from '{start_id}': {unreachable}")

    graph = {
        "nodes": [
            {"id": n.id, "text": n.text, "speaker": n.speaker, "type": n.type}
            for n in nodes
        ],
        "edges": [
            {"from": e.from_id, "to": e.to_id, "text": e.text}
            for e in edges
        ],
    }

    return graph


def _dot_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def graph_to_dot(graph: Dict[str, List[dict]]) -> str:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    node_ids = {n["id"] for n in nodes}
    include_end = any(e.get("to") == "End" for e in edges)

    out: List[str] = []
    out.append("digraph Dialogue {")
    out.append("  rankdir=LR;")

    for n in nodes:
        node_id = n["id"]
        ntype = n.get("type", "line")
        shape = "diamond" if ntype == "choice" else "box"
        speaker = n.get("speaker") or ""
        text = n.get("text") or ""
        if speaker and text:
            label = f"{node_id}\\n{speaker}: {text}"
        elif text:
            label = f"{node_id}\\n{text}"
        else:
            label = node_id
        out.append(
            f"  \"{_dot_escape(node_id)}\" [shape={shape}, label=\"{_dot_escape(label)}\"];"
        )

    if include_end and "End" not in node_ids:
        out.append('  "End" [shape=doublecircle, label="End"];')

    for e in edges:
        src = e.get("from", "")
        dst = e.get("to", "")
        label = e.get("text") or ""
        if label:
            out.append(
                f"  \"{_dot_escape(src)}\" -> \"{_dot_escape(dst)}\" [label=\"{_dot_escape(label)}\"];"
            )
        else:
            out.append(f"  \"{_dot_escape(src)}\" -> \"{_dot_escape(dst)}\";")

    out.append("}")
    return "\n".join(out) + "\n"


def main() -> None:
    with open("/app/script.txt", "r", encoding="utf-8") as f:
        script_text = f.read()

    graph = parse_script(script_text)

    with open("/app/dialogue.json", "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
        f.write("\n")

    dot = graph_to_dot(graph)
    with open("/app/dialogue.dot", "w", encoding="utf-8") as f:
        f.write(dot)


if __name__ == "__main__":
    main()
