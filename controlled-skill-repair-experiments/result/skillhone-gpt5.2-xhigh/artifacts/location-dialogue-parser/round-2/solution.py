import json
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Iterable


_SECTION_RE = re.compile(r"^\s*\[(?P<id>[^\]]+)\]\s*$")


def _split_edge(line: str) -> tuple[str, str | None]:
    if "->" not in line:
        return line.strip(), None
    left, right = line.rsplit("->", 1)
    return left.strip(), right.strip() or None


def _escape_dot_label(value: str) -> str:
    # Graphviz labels use C-like escapes; emit literal "\n" for newlines.
    value = value.replace("\\", "\\\\").replace('"', r"\"")
    return value.replace("\n", r"\n")


@dataclass(frozen=True)
class ParsedNode:
    id: str
    text: str
    speaker: str
    type: str  # 'line' or 'choice'

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "text": self.text, "speaker": self.speaker, "type": self.type}


@dataclass(frozen=True)
class ParsedEdge:
    source: str
    target: str
    text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"from": self.source, "to": self.target, "text": self.text}


def _iter_sections(lines: Iterable[str]) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []
    current_id: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_id, current_lines
        if current_id is None:
            return
        # Keep non-empty, stripped lines.
        body = [ln.strip() for ln in current_lines if ln.strip()]
        sections.append((current_id, body))
        current_id = None
        current_lines = []

    for raw in lines:
        m = _SECTION_RE.match(raw)
        if m:
            flush()
            current_id = m.group("id").strip()
            current_lines = []
            continue
        if current_id is None:
            # Ignore any leading junk outside sections.
            continue
        current_lines.append(raw.rstrip("\n"))

    flush()
    return sections


def _is_choice_block(body_lines: list[str]) -> bool:
    if not body_lines:
        return False
    for ln in body_lines:
        left, right = _split_edge(ln)
        if right is None:
            return False
        if not re.match(r"^\d+\.", left):
            return False
    return True


def _parse_line_content(line: str) -> tuple[str, str, str | None]:
    left, target = _split_edge(line)
    if ":" in left:
        speaker, text = left.split(":", 1)
        return speaker.strip(), text.strip(), target
    return "", left.strip(), target


def _validate_graph(nodes: list[ParsedNode], edges: list[ParsedEdge]) -> None:
    if not nodes:
        raise ValueError("No nodes found")

    node_ids = {n.id for n in nodes}
    errors: list[str] = []

    for e in edges:
        if e.source not in node_ids:
            errors.append(f"Edge source '{e.source}' not found")
        if e.target not in node_ids and e.target != "End":
            errors.append(f"Edge target '{e.target}' not found")

    # Reachability from first node (excluding the special 'End' sink).
    start = nodes[0].id
    adj: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        if e.target != "End":
            adj[e.source].append(e.target)

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

    unreachable = sorted(node_ids - seen)
    if unreachable:
        errors.append(
            "Unreachable nodes from start "
            f"'{start}': {', '.join(unreachable)}"
        )

    if errors:
        raise ValueError("Graph validation failed:\n" + "\n".join(errors))


def parse_script(text: str) -> dict[str, Any]:
    """Parse a dialogue script into a JSON-serializable graph.

    Returns:
        A dict with shape: {"nodes": [...], "edges": [...]}
    """
    sections = _iter_sections(text.splitlines())

    nodes: list[ParsedNode] = []
    edges: list[ParsedEdge] = []

    for node_id, body in sections:
        if _is_choice_block(body):
            nodes.append(ParsedNode(id=node_id, text="", speaker="", type="choice"))
            for ln in body:
                choice_text, target = _split_edge(ln)
                if not target:
                    raise ValueError(f"Missing edge target in choice line: {ln}")
                edges.append(ParsedEdge(source=node_id, target=target, text=choice_text))
        else:
            if not body:
                # Empty section: treat as a terminal line node.
                nodes.append(ParsedNode(id=node_id, text="", speaker="", type="line"))
                continue

            # Treat the first line as the node's content. If multiple lines exist,
            # append them as additional text (without transitions).
            speaker, first_text, target = _parse_line_content(body[0])
            extra_lines: list[str] = []
            for ln in body[1:]:
                left, maybe_target = _split_edge(ln)
                if maybe_target is not None:
                    # Multiple explicit transitions are not expected; still keep them.
                    edges.append(ParsedEdge(source=node_id, target=maybe_target, text=""))
                else:
                    extra_lines.append(left)

            text_parts = [first_text] + [ln.strip() for ln in extra_lines if ln.strip()]
            node_text = "\n".join(tp for tp in text_parts if tp)
            nodes.append(ParsedNode(id=node_id, text=node_text, speaker=speaker, type="line"))

            if target is not None:
                edges.append(ParsedEdge(source=node_id, target=target, text=""))

    _validate_graph(nodes, edges)

    return {
        "nodes": [n.to_dict() for n in nodes],
        "edges": [e.to_dict() for e in edges],
    }


def graph_to_dot(graph: dict[str, Any]) -> str:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    lines: list[str] = []
    lines.append("digraph Dialogue {")
    lines.append("  rankdir=TB;")
    lines.append("  node [fontname=Arial, fontsize=10];")
    lines.append("  edge [fontname=Arial, fontsize=8];")

    for n in nodes:
        node_id = str(n.get("id", ""))
        node_type = n.get("type", "line")
        speaker = n.get("speaker", "")
        text = n.get("text", "")

        if node_type == "choice":
            label = node_id
            shape = "diamond"
            style = "filled"
            fillcolor = "lightblue"
        else:
            preview = text
            if len(preview) > 80:
                preview = preview[:77] + "..."
            if speaker and preview:
                label = f"{node_id}\n{speaker}: {preview}"
            elif speaker:
                label = f"{node_id}\n{speaker}"
            else:
                label = node_id
            shape = "box"
            style = "rounded,filled"
            fillcolor = "white"

        lines.append(
            f"  \"{_escape_dot_label(node_id)}\" [label=\"{_escape_dot_label(label)}\", shape={shape}, style=\"{style}\", fillcolor=\"{fillcolor}\"];"
        )

    # Always include the End sink.
    lines.append('  "End" [label="END", shape=doublecircle, style="filled", fillcolor="lightgray"];')

    for e in edges:
        src = str(e.get("from", ""))
        dst = str(e.get("to", ""))
        label = str(e.get("text", "") or "")

        if label:
            lines.append(
                f"  \"{_escape_dot_label(src)}\" -> \"{_escape_dot_label(dst)}\" [label=\"{_escape_dot_label(label)}\"];"
            )
        else:
            lines.append(f"  \"{_escape_dot_label(src)}\" -> \"{_escape_dot_label(dst)}\";")

    lines.append("}")
    return "\n".join(lines) + "\n"


def _main() -> None:
    with open("/app/script.txt", encoding="utf-8") as f:
        script = f.read()

    graph = parse_script(script)

    with open("/app/dialogue.json", "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
        f.write("\n")

    dot = graph_to_dot(graph)
    with open("/app/dialogue.dot", "w", encoding="utf-8") as f:
        f.write(dot)


if __name__ == "__main__":
    _main()
