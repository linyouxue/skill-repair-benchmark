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

## Output schema (important)

Many Dialogue Graph tasks (including SkillBench-style verifiers) expect this JSON shape:

```json
{
  "nodes": [{"id": "", "text": "", "speaker": "", "type": "line|choice"}],
  "edges": [{"from": "", "to": "", "text": ""}]
}
```

Be careful with naming:

- Use edge keys **`from`** and **`to`** in exported JSON.
- Node fields are **`id`**, **`text`**, **`speaker`**, **`type`**.

## Terminal node convention: `End`

Some evaluators treat a terminal target named exactly **`"End"`** as a *special sink*:

- Edges may point to `"End"`.
- The evaluator may **not require** an explicit `"End"` node to exist.
- The evaluator may **exclude** `"End"` from reachability traversal.

Practical guidance for maximum compatibility:

- Prefer **not** to include an explicit node with `id == "End"` unless you know the evaluator expects it.
- If you do include an `End` node, ensure your own validation logic matches the evaluator’s expectations; otherwise you can create a graph that is internally “valid” but fails external reachability checks.

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
graph.add_edge(Edge(source="Start", target="Choices", text=""))

# Choice transition (with text)
graph.add_edge(Edge(source="Choices", target="End", text="1. Run away"))
```

**Important:** Even if the internal `Edge` object uses `source/target`, your exported JSON for typical verifiers should use **`from/to`**.

### 4. Export

Serialize to JSON format for the engine/verifier.

```python
data = graph.to_dict()
# Must return {"nodes": [...], "edges": [...]}
# where edges are {"from": ..., "to": ..., "text": ...}

json_str = graph.to_json()
```

### 5. Validation

Check for integrity.

```python
errors = graph.validate()
# Returns list of strings, e.g., ["Edge 'Start'->'Unk' points to missing node 'Unk'"]
```

Recommended validation checks (common in benchmarks):

1. **Edge endpoints**
   - Every edge `from` must exist in `nodes`.
   - Every edge `to` must exist in `nodes`, **except** when `to == "End"` (terminal sink convention).

2. **Reachability**
   - All non-terminal nodes must be reachable from the first node (often `Start`).
   - If the evaluator treats `End` specially, do **not** require `End` to be reachable as a node; instead, require that at least one reachable node has an outgoing edge to `End`.

3. **Choice-node semantics**
   - `type == "choice"` nodes usually have outgoing edges whose `text` is the option label (e.g., `"1. [Lie] ..."`).
   - `type == "line"` nodes typically have a single outgoing edge with `text == ""`.

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
