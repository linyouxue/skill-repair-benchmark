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



## Task-specific schema mapping (dialogue-parser)
The task validator expects **serialized edges** to use keys `from` and `to` (not `source`/`target`). Internally this library may use `Edge(source, target, text)`.

**Mapping rule:**
- `Edge.source`  → JSON `edge["from"]`
- `Edge.target`  → JSON `edge["to"]`
- `Edge.text`    → JSON `edge["text"]` (optional for simple transitions)

**Required output shape** (write to `/app/dialogue.json`):
```json
{
  "nodes": [{"id":"GateScene","text":"Halt! State your name and business.","speaker":"Guard","type":"line"}],
  "edges": [{"from":"GateScene","to":"NameChoice","text":""}]
}
```

If you use `graph.to_dict()`, ensure it produces `edges: [{"from":...,"to":...}]` or post-process the dict to rename keys before writing JSON.

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



**Important (task schema):** even if you build edges with `source`/`target`, the **serialized** form must be:
```json
{"from":"Start","to":"Choices","text":""}
```
for simple transitions, and
```json
{"from":"Choices","to":"End","text":"1. Run away"}
```
for choice edges.

### 4. Export
Serialize to JSON format for the engine.

```python
data = graph.to_dict()
# returns {"nodes": [...], "edges": [...]}
json_str = graph.to_json()
```



### DOT export (required by task)
The task requires writing a Graphviz DOT file to `/app/dialogue.dot`.

If the library provides `to_dot()`:
```python
dot = graph.to_dot()
open('/app/dialogue.dot', 'w', encoding='utf-8').write(dot)
```

Otherwise, you can generate DOT via the visualization builder/serializer your implementation uses, but ensure the result is valid DOT starting with `digraph` and contains all nodes and edges.

### 5. Validation
Check for integrity.

```python
errors = graph.validate()
# Returns list of strings, e.g., ["Edge 'Start'->'Unk' points to missing node 'Unk'"]
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



## Parsing guidance for `script.txt` format (dialogue-parser)
The parser should read a script of **sections** and **lines**:

### Sections / node headers
A new node block starts with a bracketed header:
- `[GateScene]` creates/sets the current node id to `GateScene`.

### Dialogue lines (type: `line`)
Format:
- `Speaker: some text. -> TargetNode`
Create a node with:
- `type: "line"`
- `speaker: "Speaker"`
- `text: "some text."`
And create an edge from the current node id to `TargetNode`.

If the arrow is omitted, treat it as a terminal line (no outgoing edge).

### Choice blocks (type: `choice`)
Under a header like `[NameChoice]`, lines starting with `N.` are choices:
- `1. Choice text -> TargetNode`
- `3. [Lie] I'm a merchant... -> MerchantPath`
Create a node:
- `id: "NameChoice"`, `type: "choice"`, (speaker/text may be empty)
Create one edge per choice:
- `from: "NameChoice"`
- `to: "TargetNode"`
- `text: original choice label text` (keep tags like `[Lie]`, `[Attack]` as part of `text`)

### End-to-end example
Input:
```
[GateScene]
Guard: Halt! State your name and business. -> NameChoice

[NameChoice]
1. I am Sir Aldric, Knight of the Realm. -> KnightPath
2. Just a humble traveler seeking shelter. -> TravelerPath
3. [Lie] I'm a merchant with important goods. -> MerchantPath
4. [Attack] Draw your sword! -> CombatStart
```
Output must match the task schema:
```json
{
  "nodes": [
    {"id":"GateScene","text":"Halt! State your name and business.","speaker":"Guard","type":"line"},
    {"id":"NameChoice","text":"","speaker":"","type":"choice"}
  ],
  "edges": [
    {"from":"GateScene","to":"NameChoice","text":""},
    {"from":"NameChoice","to":"KnightPath","text":"1. I am Sir Aldric, Knight of the Realm."},
    {"from":"NameChoice","to":"TravelerPath","text":"2. Just a humble traveler seeking shelter."},
    {"from":"NameChoice","to":"MerchantPath","text":"3. [Lie] I'm a merchant with important goods."},
    {"from":"NameChoice","to":"CombatStart","text":"4. [Attack] Draw your sword!"}
  ]
}
```

## Validation expectations (align to task constraints)
When implementing `graph.validate()` or a separate validator for the task, enforce:
1. **Reachability:** all nodes must be reachable from the first encountered header/node in the file.
2. **Edge targets:** every edge `to` must refer to an existing node **except** documented terminal handling (e.g., the final node may have no outgoing edges; do not create edges to missing nodes).
3. **Multiple inbound edges allowed:** many nodes (especially `End`) may have multiple incoming edges.
