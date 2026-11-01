---
name: dialogue-graph
description: A library for building, validating, visualizing, and serializing dialogue graphs. Use this when parsing scripts or creating branching narrative structures.
---

# Dialogue Graph Skill

This skill provides a `dialogue_graph` module to easily build valid dialogue trees/graphs.

## When to use

*   **Script Parsers**: When converting text to data.
*   **Dialogue Editors**: When building tools to edit conversation flow.
*   **Game Logic**: When traversing a dialogue tree.
*   **Visualization**: When generating visual diagrams of dialogue flows.

## How to use

Import the module:
```python
from dialogue_graph import Graph, Node, Edge
```

### 1. The `Graph` Class
The main container.

```python
graph = Graph()
```

### 2. Adding Nodes
Define content nodes.

```python
# Regular line
graph.add_node(Node(id="Start", speaker="Guard", text="Halt!", type="line"))

# Choice hub
graph.add_node(Node(id="Choices", type="choice"))
```

`add_node` is idempotent for identical re-registrations: calling it twice with the same `id` and attributes is a no-op (so convergence nodes like `End` can be safely re-added by multiple code paths). Re-adding the same `id` with *different* attributes still raises `ValueError`. Use `graph.ensure_node(node)` when you want strictly idempotent behavior without raising.

### 3. Adding Edges
Connect nodes (transitions).

```python
# Simple transition
graph.add_edge(Edge(source="Start", target="Choices"))

# Choice transition (with text)
graph.add_edge(Edge(source="Choices", target="End", text="1. Run away"))
```

**IMPORTANT — targets must exist as nodes.** Every edge `target` (including `End`) must correspond to a registered node. Whenever you add an edge whose target is `End`, you *must* also ensure the `End` node exists in the graph. Example:

```python
# Register the terminal node once; safe to call repeatedly thanks to ensure_node
graph.ensure_node(Node(id="End", text="", speaker="", type="line"))

graph.add_edge(Edge(source="Choices", target="End", text="1. Run away"))
graph.add_edge(Edge(source="Combat",  target="End", text=""))  # multiple paths may converge on End
```

### 4. End Node Convention

`End` is the single legal terminal node in a dialogue graph.

- **Shape**: `{"id": "End", "text": "", "speaker": "", "type": "line"}`.
- **Registration**: must appear in `graph.nodes` (not just as an edge target). Register it exactly once; use `ensure_node` so convergent branches are safe.
- **Convergence**: multiple edges may point to `End`.
- **Outgoing**: `End` may have zero outgoing edges.
- **Reachability**: `End` must still be reachable from the root (first-declared) node via the edge set.

### 5. Export
Serialize to JSON format for the engine.

```python
data = graph.to_dict()
# returns {"nodes": [...], "edges": [...]}
json_str = graph.to_json()
```

For tasks that also require a Graphviz DOT file (e.g., `/app/dialogue.dot`), use `to_dot()`:

```python
dot_src = graph.to_dot()
with open('/app/dialogue.dot', 'w', encoding='utf-8') as f:
    f.write(dot_src)
```

`to_dot()` emits:
- `shape=box` for `type=="line"` nodes,
- `shape=diamond` for `type=="choice"` nodes,
- `shape=doublecircle` for the `End` node,
- escaped labels (`\` → `\\`, `"` → `\"`, newlines → `\n`),
- an explicit declaration for the `End` node (even if it would otherwise appear only as an edge target).

> **Note**: `graph.visualize(...)` renders a PNG/SVG via the Graphviz binary with `cleanup=True`, which deletes the intermediate `.dot` file. It is **not** a substitute for `to_dot()` when a persistent `.dot` artifact is required.

### 6. Validation
Check for integrity.

```python
errors = graph.validate()
# Returns list of strings, e.g.,
#   ["Edge 'Start'->'Unk' points to missing node 'Unk'",
#    "Node 'Orphan' is not reachable from root 'Start'"]
```

`validate()` checks:
1. Every edge `source` corresponds to an existing node id.
2. Every edge `target` corresponds to an existing node id — **including `End`**, which must be a registered node.
3. All nodes are reachable from the first-declared (root) node via BFS over the directed edges.

### 7. Visualization
Generate a PNG/SVG graph diagram.

```python
# Requires: pip install graphviz
# Also requires Graphviz binary: https://graphviz.org/download/

graph.visualize('dialogue_graph')  # Creates dialogue_graph.png
graph.visualize('output', format='svg')  # Creates output.svg
```

The visualization includes:
- **Diamond shapes** for choice nodes (light blue)
- **Rounded boxes** for dialogue nodes (colored by speaker)
- **Double-circle** for the `End` node
- **Bold blue edges** for skill-check choices like `[Lie]`, `[Attack]`
- **Gray edges** for regular choices
- **Black edges** for simple transitions

Visualization reads only nodes present in `graph.nodes`; register `End` yourself (see §3/§4) to keep JSON, DOT, and PNG output consistent.

### 8. Loading from JSON
Load an existing dialogue graph.

```python
# From file
graph = Graph.from_file('dialogue.json')

# From dict
graph = Graph.from_dict({'nodes': [...], 'edges': [...]})

# From JSON string
graph = Graph.from_json(json_string)
```
