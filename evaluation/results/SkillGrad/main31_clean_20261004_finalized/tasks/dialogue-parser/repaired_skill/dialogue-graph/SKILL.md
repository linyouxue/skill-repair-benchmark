---
name: dialogue-graph
description: Build, validate, and serialize dialogue graphs with the provided dialogue_graph library, preserving script semantics while handling terminals, missing targets, and label normalization.
---

# Dialogue Graph Skill

## Plan and verify (use once per task)

1. Prefer the provided domain library over bespoke schemas: build with `dialogue_graph.Graph/Node/Edge`, validate with `Graph.validate()`, and serialize with `to_dict()`/`to_json()`.
2. Inspect the actual input artifact before coding: load the full script text and identify node IDs, node types (line vs choice), and any terminal convention.
3. If a tool call to read critical input fails (tool error, wrong schema, empty output), immediately retry using the correct tool interface until the content is confirmed loaded; do not proceed on guesses.
4. Normalize presentation artifacts early (e.g., numbering prefixes on choices) so labels match expected schema.
5. Preserve the script faithfully: build the full node/edge set from the input as written; treat reachability/missing-target issues as diagnostics unless the task explicitly asks you to transform/prune.
6. Run `Graph.validate()` and a serialization round-trip check before writing final output; if either disagrees with your expectations, treat the library as the source of truth and adjust the graph (not the validator).
7. Before termination, run a deliverables checklist: required functions exist (e.g., `parse_script(text: str)` is implemented/exported) and required output files are written, non-empty, and generated from the same graph.

## Use the provided `dialogue_graph` types (avoid schema drift)

Use the library end-to-end so its serialization and validation semantics match hidden tests. Avoid writing parallel schemas, custom validators, or handcrafted JSON.

```python
from dialogue_graph import Graph, Node, Edge

g = Graph()
g.add_node(Node(id="n1", type="line", speaker="S", text="..."))
g.add_node(Node(id="n2", type="choice"))
g.add_edge(Edge(source="n1", target="n2"))

assert not g.validate(), "fix reported issues, then re-run validate()"
payload = g.to_dict()
assert Graph.from_dict(payload).to_dict() == payload, "schema drift: rebuild via library types"
```

Decision rule: if you are about to assemble dicts/JSON for nodes or edges, stop and switch to `Node`/`Edge` + `Graph.to_dict()`; only derive other formats (e.g., DOT) from the library object or its `to_dict()` output.

Read references/use-library-end-to-end.md when you are about to write a custom parser/validator/serializer for dialogue graphs, generate DOT from a bespoke structure, or change semantics based on a small snippet test. Skip when the task explicitly requires a different schema than `dialogue_graph` exports.

## Normalize choice edge labels

Choice numbering like `1.` is usually a rendering artifact; normalize to the user-facing label before setting `Edge.text`.

```python
import re

def normalize_choice_label(label: str) -> str:
    return re.sub(r"^\s*\d+\.\s*", "", label).strip()

edge_text = normalize_choice_label(raw_label)
```

Decision rule: preserve semantic tokens (e.g., bracketed tags) if they are part of the choice content, but strip ordinal numbering.

Read references/normalize-choice-labels.md when the input choices are numbered or bulleted and edges require `text`. Skip when the input already provides clean labels without numbering.

## Preserve the full script (no pruning by default)

Pruning unreachable nodes/edges is a semantic transformation that can fail validators expecting a faithful parse.

```python
# After parsing, keep all parsed nodes/edges.
# If you need reachability info, compute it separately.
seen = set()
stack = [start_id]
while stack:
    cur = stack.pop()
    if cur in seen:
        continue
    seen.add(cur)
    stack.extend(adj.get(cur, ()))
```

Decision rule: only prune when the task explicitly asks for a reachable subgraph; otherwise report unreachable IDs (or leave them) and keep the full graph.

Read references/preserve-script-no-pruning.md when you are tempted to delete nodes/edges to “fix” validation or to match reachability. Skip when the required output is explicitly a reachable subgraph.

## Terminal handling (do not fabricate nodes by default)

Terminal targets may be a special convention (implicit sink) or an explicit node in the input. Do not create missing nodes just to satisfy homegrown checks; follow the library/spec convention.

```python
TERMINAL_IDS = {"End", "END", "end"}

def is_terminal(node_id: str) -> bool:
    return node_id in TERMINAL_IDS

# When you see an edge to a missing target:
# - if it is terminal by convention, allow it without creating a node
# - otherwise, treat it as a parse/input error (do not create placeholders)
```

Decision rule: if `Graph.validate()` complains about a missing terminal node, add the terminal node explicitly with whatever type/fields the library requires; if it allows terminal references, keep it implicit.

Read references/terminal-conventions.md when edges point to a terminal like `End` or when validation reports a missing target for a terminal. Skip when all edge targets are explicit nodes in the input.

## Common Pitfalls

- Mis-invoking tools to read required inputs, then proceeding without actually loading the script and terminating without writing deliverables.
- Reimplementing node/edge schemas, serialization, or validation instead of using the provided library end-to-end, causing subtle mismatches that pass eyeballing but fail hidden validators.
- Generating other outputs (e.g., DOT) from a bespoke intermediate structure instead of from the library object or `Graph.to_dict()`.
- "Fixing" missing edge targets by fabricating placeholder nodes (except for a spec-approved terminal convention like `End`).
- Pruning unreachable nodes/edges to satisfy a local check when the expected output is a faithful parse of the full script.
- Leaving choice numbering (e.g., `1.`) in edge labels when the expected schema treats numbering as non-semantic.
