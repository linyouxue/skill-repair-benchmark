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

```

### 4. Export
Serialize to JSON format for the engine.

```python
data = graph.to_dict()
# returns {"nodes": [...], "edges": [...]}
json_str = graph.to_json()
```

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



## 8. Script parsing workflow

Implement `parse_script(text: str)` as the deterministic entry point for the script-parser task. It must return a dictionary with exactly the top-level collections `nodes` and `edges`, in insertion order, using the serialized schemas below. A caller can write the returned dictionary to `/app/dialogue.json` with JSON serialization and generate `/app/dialogue.dot` from the same graph.

### Input forms

Process the input line by line. Ignore blank lines, including blank lines between scenes. A line matching a bracketed header such as `[GateScene]` starts a new scene or node context whose label is `GateScene`. A speaker line has the form `Speaker: dialogue text -> Target`; split at the first colon and the final arrow, trim surrounding whitespace, and preserve the dialogue text otherwise. A numbered choice has the form `N. choice text -> Target`, where `N` is one or more digits. Choices belong to the current header/context and must be parsed in their numeric source order.

A choice may begin with a tag such as `[Lie]` or `[Attack]`. Remove only the numeric prefix and surrounding separator whitespace; preserve the optional bracketed tag as part of the choice edge text, consistently and exactly (for example, retain `[Lie]` rather than discarding it). Blank lines do not create nodes or edges. Reject malformed nonblank content instead of silently creating an unrelated node.

### Deterministic nodes and edges

Use the first parsed node as the graph root. Create nodes and edges in source-file order. Every node object has the fields `id`, `text`, `speaker`, and `type`; every edge object has exactly `from`, `to`, and `text`.

Use header labels as the stable context/choice identifiers. For a speaker line, create a line node with a deterministic ID based on its context and occurrence (for example, the context label for the first line and a monotonically numbered suffix for subsequent lines); retain that ID for the entire parse and never use random values or memory addresses. Its `text` is the dialogue text, its `speaker` is the text before the colon, and its `type` is `line`. Add an edge from that line node to the arrow target, with an empty edge `text`.

For a context containing numbered choices, create one explicit choice node with a deterministic ID based on the header label (adding a stable occurrence suffix if the same label is repeated), `text` and `speaker` set to empty strings, and `type` set to `choice`. Connect the preceding line node in that context to the choice node with an empty edge text when such a line exists. Add one edge per numbered choice from the choice node to the stated target; the edge `text` is the normalized choice text including any leading tag. Choice targets are ordered by their appearance in the file, not by dictionary ordering.

Create target placeholders deterministically when a target is referenced before its header or body is encountered, so every nonterminal edge target can be resolved. A target named `End` is terminal: it may be used by multiple edges and does not require a dialogue body. Do not invent dialogue text or speakers for unresolved nonterminal targets; instead, require a corresponding header/context or otherwise report the missing target during validation. Header/context nodes that are not otherwise represented by a line or choice must still have a deterministic node record if they are referenced as targets.

When constructing the graph through `Graph`, `Node`, and `Edge`, convert the library's `source` and `target` fields to the serialized keys `from` and `to` before returning or writing JSON. The returned node and edge lists must retain insertion order.

### Validation and output

Before writing `/app/dialogue.json`, validate all of the following:

* node IDs are unique and every node has exactly the required node fields;
* every edge has exactly `from`, `to`, and `text`, and its `from` node exists;
* every nonterminal edge target exists; `End` is the only permitted terminal target;
* every node is reachable from the first parsed node, using directed edges;
* multiple distinct edges to `End` are valid;
* choice nodes have their explicitly parsed outgoing choice edges.

Raise or return a clear validation error rather than emitting a partially valid graph. Serialize the validated dictionary as `/app/dialogue.json`. Generate `/app/dialogue.dot` with one DOT node per graph node and one directed DOT edge per graph edge; escape quotes, backslashes, and newlines in labels. Use node IDs as DOT identifiers and include the dialogue or choice text in labels where available. Tests call `parse_script(text: str)` directly, so it must perform parsing and return the dictionary independently of the command-line/file-writing wrapper.
