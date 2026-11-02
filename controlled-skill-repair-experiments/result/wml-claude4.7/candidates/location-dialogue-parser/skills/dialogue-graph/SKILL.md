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

### 3. Adding Edges

Connect nodes (transitions). Every edge's `target` must correspond to a declared node id — including the shared terminal sink `End`. If one or more branches terminate at `End`, declare it once as a node **before** any edge references it. This keeps the "all edge targets exist" and "all nodes reachable from the first node" contracts simultaneously satisfiable, and ensures `End` appears in the exported `nodes` list.

```python
# Declare the terminal sink exactly once, before referencing it as a target.
graph.add_node(Node(id="End", type="line"))

# Simple transition
graph.add_edge(Edge(source="Start", target="Choices"))

# Choice transition (with text) terminating at the shared End sink
graph.add_edge(Edge(source="Choices", target="End", text="1. Run away"))
```

This `End`-declaration convention is only a relaxation for the explicitly terminal sink. Non-terminal unresolved targets (typos, forward references that are never added as nodes) must still be treated as errors by `validate()` and fixed, not auto-accepted.

### 4. Export

Serialize the graph to JSON **and** persist it to the caller-requested file path. The exported schema is:

```
{
  "nodes": [{"id": "", "text": "", "speaker": "", "type": ""}, ...],
  "edges": [{"from": "", "to": "", "text": ""}, ...]
}
```

Always run `validate()` first and ensure it returns `[]` so the delivered artifact is schema-valid.

```python
# 1. Validate before writing — delivered artifacts must be schema-valid.
errors = graph.validate()
assert errors == [], errors

# 2. Serialize.
data = graph.to_dict()          # dict shaped as above (for in-memory callers)
json_str = graph.to_json()      # same shape, as a JSON string

# 3. Writeback contract: write to the caller-specified path
#    (e.g. the task may require /app/dialogue.json).
with open('/app/dialogue.json', 'w', encoding='utf-8') as f:
    f.write(json_str)
```

In-memory callers (editors, tests) that do not need an on-disk file may stop after step 2; the writeback step is only mandatory when a file path is part of the delivery contract.

### 5. Validation
Check for integrity.

```python
errors = graph.validate()
# Returns list of strings, e.g., ["Edge 'Start'->'Unk' points to missing node 'Unk'"]
```

### 6. Visualization

Two distinct deliverables are supported — do not confuse them:

* **DOT source** (`.dot` text file) — the raw Graphviz source, for downstream tooling or human inspection. Produce via `graph.to_dot()` and write the returned string to the caller's `.dot` path. This path does **not** require the Graphviz system binary.
* **Rendered image** (PNG/SVG/PDF) — a preview. Produce via `graph.visualize(...)`; this path renders the image and cleans up the intermediate `.dot` file, so it is **not** a substitute for `to_dot()` when a `.dot` file is the required deliverable.

```python
# Emit raw DOT source to the caller-specified .dot path
# (e.g. the task may require /app/dialogue.dot).
dot_source = graph.to_dot()
with open('/app/dialogue.dot', 'w', encoding='utf-8') as f:
    f.write(dot_source)

# Optional: render a PNG/SVG preview.
# Requires: pip install graphviz
# Also requires Graphviz binary: https://graphviz.org/download/
graph.visualize('dialogue_graph')          # Creates dialogue_graph.png
graph.visualize('output', format='svg')    # Creates output.svg
```

Both the `to_dot()` source and the rendered image include:
- **Diamond shapes** for choice nodes (light blue)
- **Rounded boxes** for dialogue nodes (colored by speaker)
- **Bold blue edges** for skill-check choices like `[Lie]`, `[Attack]`
- **Gray edges** for regular choices
- **Black edges** for simple transitions

### 7. Loading from JSON
Load an existing dialogue graph.

```python
# From file
graph = Graph.from_file('dialogue.json')

# From dict
graph = Graph.from_dict({'nodes': [...], 'edges': [...]})

# From JSON string
graph = Graph.from_json(json_string)
```
