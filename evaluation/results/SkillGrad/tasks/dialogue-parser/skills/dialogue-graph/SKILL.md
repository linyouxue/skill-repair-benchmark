---
name: dialogue-graph
description: Build, validate, visualize, and serialize dialogue graphs while reliably writing all grader-required on-disk artifacts.
---

# Dialogue Graph Skill

## Plan the run (minimal)

1. Identify the required deliverables (filenames + **absolute** paths) before you start changing code.
2. Build/parse into an in-memory graph/dict first; write files only after you have a coherent best-effort structure.
3. **End-of-run guardrail (hard stop):** immediately before `end_turn`, you must run **export → artifact check** and **log the results** for each required path: `exists`, `size>0`, and `reload/parse` (e.g., `json.load` for JSON; DOT starts with `digraph`). **Do not call** `end_turn` until you have re-opened the required files and confirmed they load/parse.
   - Required paths must be stated explicitly (not “the outputs”).

Read references/export-and-artifact-check.md when the grader requires specific on-disk artifacts at exact paths. Skip when outputs are returned directly (no filesystem deliverables).

## Build a graph data model

Use a small, explicit model (nodes + edges) so validation and exports are simple.

```python
from dialogue_graph import Graph, Node, Edge

g = Graph()
g.add_node(Node(id="N1", type="line", speaker="A", text="..."))
g.add_node(Node(id="N2", type="choice"))
g.add_edge(Edge(source="N1", target="N2"))

data = g.to_dict()
```

Decision rule: prefer `Graph` when you need validation/export helpers; use a plain dict only when the task explicitly forbids external structures.

## Validate before exporting

Validate graph integrity (missing nodes, malformed edges) before writing outputs.

```python
g_errors = g.validate()
if g_errors:
    raise ValueError("Invalid dialogue graph: " + "; ".join(g_errors))
```

## Export to JSON

Serialize to a Python dict/JSON string suitable for downstream use.

```python
payload = g.to_dict()
json_text = g.to_json()
```

## Export to Graphviz DOT

When a `.dot` file (not just a PNG/SVG) is required, write DOT source explicitly.

```python
lines = ["digraph Dialogue {", "  rankdir=LR;"]
for n in g.nodes.values():
    lines.append(f'  "{n.id}";')
for e in g.edges:
    lines.append(f'  "{e.source}" -> "{e.target}";')
lines.append("}")
dot_text = "\n".join(lines)
```

## Common Pitfalls

- Finishing “logic” but not materializing required deliverables (JSON/DOT) at the specified paths; always perform a post-write artifact check with a hard stop before ending.
- Writing visualization outputs (PNG/SVG) when the evaluator expects DOT source.
- Skipping validation: exporting a graph with edges pointing to missing node IDs.
