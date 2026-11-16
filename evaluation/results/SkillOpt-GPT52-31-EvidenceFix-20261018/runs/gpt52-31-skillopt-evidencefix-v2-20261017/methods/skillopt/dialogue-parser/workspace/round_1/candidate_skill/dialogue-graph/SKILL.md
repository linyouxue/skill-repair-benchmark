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

```python
# Simple transition
graph.add_edge(Edge(source="Start", target="Choices"))

# Choice transition (with text)
graph.add_edge(Edge(source="Choices", target="End", text="1. Run away"))
```



### Terminal / Sentinel Targets (e.g., `End`)
Some dialogue formats use a **sentinel terminal target** like `"End"` to mean "stop the conversation".

**Convention for exported graphs:**
- Treat sentinel terminals (commonly `"End"`) as **legal edge targets**.
- **Do not emit** sentinel terminals as concrete nodes in `nodes` unless the downstream engine/evaluator explicitly treats them as traversable nodes.

Why: some validators exclude traversal into `"End"` while still requiring every emitted node to be reachable; creating an `End` node can therefore guarantee an "unreachable node" failure.

Practical rule:
- Keep edges like `Choices -> End`.
- Omit an `End` node from `nodes` for evaluators that treat `End` as a non-traversed terminal.

### 4. Export
Serialize to JSON format for the engine.

```python
data = graph.to_dict()
# returns {"nodes": [...], "edges": [...]}
json_str = graph.to_json()
```



#### Schema mapping note (Python objects ↔ JSON)
This skill uses `Edge(source, target)` in Python examples. Many tasks/export formats expect JSON edge keys named `"from"` and `"to"`.

When exporting to such a schema, map:
- `edge.source` → `edge_dict["from"]`
- `edge.target` → `edge_dict["to"]`
- `edge.text` → `edge_dict["text"]` (if present)

Example JSON edge:
```json
{"from": "Choices", "to": "End", "text": "1. Run away"}
```

### 5. Validation
Check for integrity.

```python
errors = graph.validate()
# Returns list of strings, e.g., ["Edge 'Start'->'Unk' points to missing node 'Unk'"]
```



#### Validator guidance for reachability with sentinel terminals
If your format uses terminal sentinels (e.g., `"End"`), reachability checks should typically:
- start from the entry node (often the first/`Start` node),
- **not traverse into sentinel terminals**, and
- **not require** sentinel terminals to be present in `nodes`.

Illustrative pseudocode:
```python
SENTINELS = {"End"}

# Edge targets must exist unless they are sentinels
for e in edges:
    if e.target not in SENTINELS:
        assert e.target in node_ids

# Reachability ignores sentinels
reachable = set()
queue = [start_id]
while queue:
    n = queue.pop(0)
    if n in reachable:
        continue
    reachable.add(n)
    for tgt in outgoing_targets.get(n, []):
        if tgt not in SENTINELS:
            queue.append(tgt)

# Unreachable is computed over emitted nodes only
unreachable = set(node_ids) - reachable
assert not unreachable
```

### 6. Visualization
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
