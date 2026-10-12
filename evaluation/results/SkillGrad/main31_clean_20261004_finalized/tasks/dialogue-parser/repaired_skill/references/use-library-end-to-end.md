---
description: Use the provided dialogue_graph library end-to-end to avoid schema drift; preserve script semantics, rely on Graph.validate() for fixes, and serialize/derive DOT only from library outputs.
---

# Use `dialogue_graph` end-to-end (no bespoke schemas)

## Trigger

Load this when you are tempted to:
- build `{nodes:[...], edges:[...]}` dicts directly,
- write a custom validator to “repair” graphs,
- prune/normalize semantics beyond what the spec asks,
- generate DOT from a bespoke intermediate structure.

## Procedure

1. **Parse → construct library objects only.** Create `Node` and `Edge` instances; add them to a `Graph`. Avoid parallel `_Node/_Edge` dataclasses or dict schemas.
2. **Preserve semantics by default.** Do not prune nodes/edges or invent nodes (except if the library explicitly requires a terminal).
3. **Validate with the library and fix only what it reports.** Treat `Graph.validate()` as the authoritative ruleset.
4. **Round-trip serialization to detect drift.** `Graph.from_dict(Graph.to_dict())` should preserve the payload.
5. **Emit all downstream formats from the library payload.** If DOT is needed, generate it from `g` or `g.to_dict()` so it stays coupled to the official schema.

```python
from dialogue_graph import Graph, Node, Edge

def build_graph(node_rows, edge_rows):
    g = Graph()
    for r in node_rows:
        g.add_node(Node(**r))
    for r in edge_rows:
        g.add_edge(Edge(**r))
    return g

g = build_graph(node_rows, edge_rows)
errors = g.validate()
if errors:
    raise ValueError(f"graph invalid per library: {errors}")

payload = g.to_dict()
rt = Graph.from_dict(payload).to_dict()
assert rt == payload, "round-trip mismatch: stop using bespoke structures; rebuild via Node/Edge"
```

## Runtime branch

- **If `Graph.validate()` reports missing targets:**
  - If the target is a spec-approved terminal (e.g., `End`) and the library expects an explicit terminal node, add the terminal node with the **library-required** type/fields.
  - Otherwise, treat it as an input/parse error; do **not** fabricate placeholder nodes.

- **If `Graph.validate()` passes but hidden tests previously failed:**
  - Remove any semantic “fixups” you added (pruning, auto-terminals, rewriting IDs/labels beyond normalization) and regenerate the payload strictly via `to_dict()`.

## Verification

- **Primary:** `g.validate()` returns empty.
- **Compatibility check:** `Graph.from_dict(g.to_dict()).to_dict() == g.to_dict()`.

If either check fails: stop generating custom dicts/DOT; rebuild the graph by (a) constructing only library `Node`/`Edge` objects, then (b) applying only the minimal edits needed to satisfy `Graph.validate()`.
