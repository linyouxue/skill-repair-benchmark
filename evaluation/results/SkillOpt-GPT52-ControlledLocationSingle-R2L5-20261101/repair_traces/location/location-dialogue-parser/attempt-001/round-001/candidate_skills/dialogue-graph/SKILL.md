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
Connect nodes (transitions).

**Constructor vs. wire format mapping**
- In Python, edges are created with `Edge(source=..., target=..., text=...)`.
- When serialized (via `to_dict()` / `to_json()`), edges are emitted using **canonical keys**: `{"from": ..., "to": ..., "text": ...}`.
  - `source` → `from`
  - `target` → `to`
  - `text` is optional (omit or set to `""` if not applicable)

```python
# Simple transition (no label text)
graph.add_edge(Edge(source="Start", target="Choices"))

# Choice transition (edge label text)
graph.add_edge(Edge(source="Choices", target="End", text="1. Run away"))
```

**"End" convention (terminal target)**
- The string `"End"` is a **reserved terminal target**.
- You may create edges whose `target`/`to` is `"End"` **without** adding a corresponding `Node(id="End", ...)`.
- Validation should allow `to == "End"` as the only missing-target exception (all other edge targets must exist).

### 4. Export
Serialize to JSON format for the engine.

**Canonical JSON schema (wire format)**
The exported structure is always:
```json
{
  "nodes": [
    {"id": "...", "text": "...", "speaker": "...", "type": "line|choice"}
  ],
  "edges": [
    {"from": "...", "to": "...", "text": "..."}
  ]
}
```
Notes:
- Node fields:
  - `id` (string, required)
  - `type` (string, required; typically `"line"` or `"choice"`)
  - `speaker` (string, optional/empty for non-line nodes)
  - `text` (string, optional/empty for choice hubs)
- Edge fields:
  - `from` (string, required)
  - `to` (string, required; may be the reserved terminal `"End"`)
  - `text` (string, optional; used for choice labels)

```python
data = graph.to_dict()  # -> {"nodes": [...], "edges": [...]} using the schema above
json_str = graph.to_json()
```

### 5. Validation
Check for integrity.

```python
errors = graph.validate()
# Returns list of strings, e.g., ["Edge 'Start'->'Unk' points to missing node 'Unk'"]



Validation rules expected by downstream consumers/parsers:
- All nodes must be reachable from the first node.
- All edge targets must exist **except** the reserved terminal target `"End"`.
- Multiple paths may lead to `"End"`.
```

### 6. Visualization
Generate a PNG/SVG graph diagram.

```python
# Requires: pip install graphviz
# Also requires Graphviz binary: https://graphviz.org/download/

graph.visualize('dialogue_graph')          # Creates dialogue_graph.png
graph.visualize('output', format='svg')    # Creates output.svg
```

The visualization includes:
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
