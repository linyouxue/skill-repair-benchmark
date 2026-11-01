---
name: skilltta-task-guidance
description: Task-guidance skill for building a dialogue script parser that emits a validated JSON graph and a Graphviz .dot visualization.
---

# Dialogue Graph Parser — Task Guidance

## Goal
Implement `solution.py` with `def parse_script(text: str)` that reads `/app/script.txt`, produces `/app/dialogue.json` and `/app/dialogue.dot`. Returned object must be a dict `{"nodes": [...], "edges": [...]}`.

## Input Format Recap
- Scene/node header: `[NodeId]` on its own line.
- Line node: `Speaker: text -> TargetNode` (one speaker line immediately after a header).
- Choice node: multiple lines starting with `N. ` (digits + dot) under a header; each option may contain a bracketed tag like `[Lie]` or `[Attack]` and ends with `-> TargetNode`.
- Blank lines separate blocks.

## Parsing Rules
1. Split into blocks by `[Header]`. The first header is the entry/root node.
2. For a block:
   - If the body is a single `Speaker: text -> Target` line → create a node with `type:"line"`, `speaker:<Speaker>`, `text:<text without arrow>`, and one edge `{from: id, to: Target, text: ""}`.
   - If the body contains numbered options → create a node with `type:"choice"`, `speaker:""`, `text:""` (or the preceding prompt if any). For each option, add an edge `{from: id, to: Target, text: <option text, keep bracket tag>}`.
3. Preserve option order. Strip the leading `N.` and the trailing `-> Target` when storing edge `text`.
4. Trim whitespace everywhere; keep bracket tags (e.g., `[Lie]`) inside edge `text`.

## Adding Edges — IMPORTANT
- Always emit an edge for every `-> Target`, even when `Target == "End"`.
- Do **not** silently drop edges that point to `End`. Instead, ensure the `End` node exists as a synthetic terminal node: `{"id":"End", "text":"", "speaker":"", "type":"line"}` (added once, deduplicated). Multiple edges may converge on `End`.
- Every edge must have `from`, `to`, `text` keys (use empty string when no label).
- Deduplicate nodes by `id`; if a target id is referenced but never defined (other than `End`), treat it as a validation error unless it is the terminal.

## Validation Constraints
1. All nodes reachable from the first (root) node via BFS over edges.
2. Every edge `to` must correspond to an existing node id (after injecting `End`).
3. `End` may have no outgoing edges; it is the only legal "sink without definition in script".

## Export — IMPORTANT
- Write `/app/dialogue.json` using `json.dump(graph, f, ensure_ascii=False, indent=2)`.
- Write `/app/dialogue.dot` with:
  ```
  digraph Dialogue {
    rankdir=LR;
    "NodeId" [label="...", shape=box|diamond];
    "From" -> "To" [label="edge text"];
  }
  ```
  - `shape=box` for `line`, `shape=diamond` for `choice`, `shape=doublecircle` for `End`.
  - Escape `"` and backslashes inside labels; replace newlines with `\\n`.
  - Emit the `End` node declaration explicitly so Graphviz renders it even if only referenced by edges.

## Reference Skeleton
```python
import json, re, os

HEADER_RE = re.compile(r'^\[([^\]]+)\]\s*$')
OPTION_RE = re.compile(r'^\s*\d+\.\s*(.*?)\s*->\s*(\S+)\s*$')
LINE_RE   = re.compile(r'^\s*([^:]+):\s*(.*?)\s*->\s*(\S+)\s*$')

def parse_script(text: str):
    nodes, edges, seen = [], [], set()
    def add_node(n):
        if n['id'] in seen: return
        seen.add(n['id']); nodes.append(n)

    blocks, cur = [], None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        m = HEADER_RE.match(line)
        if m:
            cur = {'id': m.group(1).strip(), 'body': []}
            blocks.append(cur)
        elif cur is not None:
            cur['body'].append(line)

    for b in blocks:
        nid, body = b['id'], b['body']
        opts = [OPTION_RE.match(l) for l in body]
        if body and all(opts):
            add_node({'id': nid, 'text': '', 'speaker': '', 'type': 'choice'})
            for m in opts:
                edges.append({'from': nid, 'to': m.group(2), 'text': m.group(1)})
        else:
            m = LINE_RE.match(body[0])
            add_node({'id': nid, 'text': m.group(2), 'speaker': m.group(1).strip(), 'type': 'line'})
            edges.append({'from': nid, 'to': m.group(3), 'text': ''})

    # Inject End if referenced
    targets = {e['to'] for e in edges}
    if 'End' in targets:
        add_node({'id': 'End', 'text': '', 'speaker': '', 'type': 'line'})

    return {'nodes': nodes, 'edges': edges}

def to_dot(g):
    def esc(s): return s.replace('\\', '\\\\').replace('"', '\\"')
    out = ['digraph Dialogue {', '  rankdir=LR;']
    for n in g['nodes']:
        shape = 'doublecircle' if n['id']=='End' else ('diamond' if n['type']=='choice' else 'box')
        label = esc(f"{n['id']}" + (f": {n['speaker']}" if n['speaker'] else ''))
        out.append(f'  "{n["id"]}" [label="{label}", shape={shape}];')
    for e in g['edges']:
        out.append(f'  "{e["from"]}" -> "{e["to"]}" [label="{esc(e["text"])}"];')
    out.append('}')
    return '\n'.join(out)

if __name__ == '__main__':
    with open('/app/script.txt') as f: text = f.read()
    g = parse_script(text)
    with open('/app/dialogue.json','w') as f: json.dump(g, f, ensure_ascii=False, indent=2)
    with open('/app/dialogue.dot','w') as f: f.write(to_dot(g))
```

## Common Pitfalls (addressed by location hint)
- **Adding Edges**: forgetting to emit edges whose target is `End`, or omitting the `text` key.
- **Export**: not creating `/app/dialogue.dot`, or not declaring the `End` node in the DOT output.
- **End handling**: treating `End` as an error instead of a legal terminal node; failing to dedupe when multiple branches point to `End`.

## Lessons from Retrieved JSON Examples
- Always `json.dump` to the exact required path and validate structure before returning (BigCodeBench/398, /30).
- Return the in-memory dict alongside writing files, mirroring `task_func` patterns (BigCodeBench/490).
- Guard file I/O; create parent dirs if missing; use UTF-8.
