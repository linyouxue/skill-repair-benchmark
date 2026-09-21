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

### 4. Export
Serialize to JSON format for the engine.

```python
data = graph.to_dict()
# Before serialization, convert Edge(source, target, text) objects to:
# {"from": source, "to": target, "text": text}
# The evaluator-facing JSON is exactly:
# {"nodes":[{"id":"","text":"","speaker":"","type":""}],
#  "edges":[{"from":"","to":"","text":""}]}
json_str = json.dumps(data, sort_keys=False, separators=(",", ":"))
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



## Task-oriented script parsing contract

For the parser task, implement `def parse_script(text: str)` in `/app/solution.py`. It may return the dictionary directly or a `Graph`, but the final serialized object must have exactly the top-level keys `nodes` and `edges`, with node objects containing exactly `id`, `text`, `speaker`, and `type`, and edge objects containing exactly `from`, `to`, and `text`.

### Grammar and deterministic construction

Parse the input line by line after normalizing newlines. Ignore blank lines, but do not silently ignore nonblank malformed lines. The supported forms are:

```text
[SceneId]
Speaker: dialogue text -> Target
N. choice text -> Target
N. [Tag] choice text -> Target
```

`SceneId`, `Speaker`, and `Target` are nonempty strings without the surrounding brackets, colon, or arrow. A choice number is one or more decimal digits followed by a period. The arrow target is required on every dialogue and choice line. Split dialogue at the final valid ` -> ` separator so dialogue text can contain other punctuation; split a choice similarly. Trim surrounding whitespace from fields.

Headers are labels, not emitted nodes. Maintain a label table from each header identifier to the first generated node for that section. A section containing choices maps its header to one choice hub; a section containing dialogue maps its header to its first line node. Reject duplicate headers. A target must resolve to a header label or the special terminal target `End`.

Create dialogue nodes in source order with deterministic IDs `line_001`, `line_002`, and so on. Their `type` is `line`, `speaker` is the parsed speaker, and `text` is the dialogue text without the arrow and target. For consecutive dialogue lines in one section, add a simple edge from each line to the next line. The final dialogue line's target edge goes to the resolved target.

For each contiguous block of numbered choices, create one deterministic hub node with ID `choice_<SceneId>` (use a collision-safe deterministic suffix if the same sanitized ID would collide). Its `type` is `choice`, and its `text` and `speaker` are empty strings. The section label resolves to this hub. Add one edge from the hub for each choice in source order. The edge `text` is the trimmed choice text after the numeric prefix, including an optional bracketed tag such as `[Lie]` or `[Attack]`; preserve the tag exactly rather than discarding it. Choice numbers determine ordering and are not required in the edge text. Repeated destinations are valid and must produce separate edges. Do not create implicit nodes for choices: all choice destinations resolve through the label table or `End`.

When `End` is referenced, create exactly one terminal node with ID `End`, empty `text` and `speaker`, and `type` `terminal` if it is not already present. `End` is the only permitted unresolved target and may have multiple incoming edges. A literal `[End]` header is not needed and should be rejected as a duplicate/conflicting terminal declaration. The first generated line or choice hub in the first section is the graph's start node.

Use stable source order for nodes and edges: line nodes and hubs are emitted in the order their sections/content first appear, and edges are emitted in construction order. Do not use hash iteration order for serialization. Convert library `Edge(source, target, text)` values explicitly to `{"from": edge.source, "to": edge.target, "text": edge.text}`; never expose `source` or `target` in the final JSON.

### Errors and validation

Raise a clear `ValueError` containing the 1-based input line number for malformed nonblank lines, including an invalid header, missing speaker colon, missing `->` target, missing choice number, empty choice text, or empty target. Reject an unknown non-terminal target with an error identifying the source and target. Reject duplicate labels. A section must contain at least one valid dialogue line or choice block.

After construction, validate that every non-terminal edge target exists, that every generated node is reachable from the first parsed node, and that the special `End` node is allowed as a terminal target. Multiple paths to `End` must remain valid. Report missing targets and unreachable node IDs explicitly instead of silently repairing them.

### Required files and DOT output

When run as the task solution, read `/app/script.txt`, call `parse_script`, validate the result, and write stable JSON to `/app/dialogue.json` using UTF-8 and deterministic separators. Also write `/app/dialogue.dot`. The DOT graph must contain the same nodes and edges as the JSON, use quoted IDs, escape backslashes, quotes, and newlines in labels, and use edge labels from the serialized `text` field. Give `choice` nodes a distinct shape (for example `diamond`), terminal nodes a distinct shape, and line nodes a readable shape; styling must not change graph semantics.

### Representative example and tests

For the input:

```text
[GateScene]
Guard: Halt! State your name and business. -> NameChoice

[NameChoice]
1. I am Sir Aldric, Knight of the Realm. -> KnightPath
2. Just a humble traveler seeking shelter. -> TravelerPath
3. [Lie] I'm a merchant with important goods. -> MerchantPath
4. [Attack] Draw your sword! -> CombatStart
```

`GateScene` resolves to a `line_001` node, `NameChoice` resolves to its choice hub, and the hub has four ordered outgoing edges whose texts retain `[Lie]` and `[Attack]`. The parser must also be tested with ordinary dialogue lines, tagged and untagged choices, repeated destinations, a terminal `-> End`, multiple incoming edges to `End`, an unknown target, an unreachable section, and malformed lines such as `Guard: missing target`. Tests should assert exact node/edge keys, deterministic IDs and ordering, preservation of choice tags, and matching JSON/DOT edge semantics.
