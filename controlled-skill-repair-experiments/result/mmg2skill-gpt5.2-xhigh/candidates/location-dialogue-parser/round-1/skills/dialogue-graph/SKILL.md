---
name: dialogue-graph
description: A library for building, validating, visualizing, and serializing dialogue
  graphs (line + choice nodes) using `Graph`, `Node`, and `Edge`.
---

## Steps
1. Import the primitives and create a graph:
   ```python
   from dialogue_graph import Graph, Node, Edge
   graph = Graph()
   ```
2. Add nodes (use unique IDs; add them in script order if you want a stable “first node” entry point):
   ```python
   # Regular spoken/narration line node
   graph.add_node(Node(id="GateScene", speaker="Guard", text="Halt!", type="line"))

   # Choice hub node
   graph.add_node(Node(id="NameChoice", type="choice"))
   ```
3. Add edges to connect nodes:
   - For non-choice transitions, keep `text` empty (the spoken text belongs on the node):
     ```python
     graph.add_edge(Edge(source="GateScene", target="NameChoice", text=""))
     ```
   - For choice options, set `Edge.text` to the option body **without** the numeric enumeration (`1.` / `2.` / …). Keep bracket tags like `[Lie]` / `[Attack]` as part of the option body text:
     ```python
     graph.add_edge(Edge(source="NameChoice", target="KnightPath",
                         text="I am Sir Aldric, Knight of the Realm."))
     graph.add_edge(Edge(source="NameChoice", target="MerchantPath",
                         text="[Lie] I'm a merchant with important goods."))
     ```
   - Use `"End"` as a terminal edge target string; it is treated as a special terminal and does not require a corresponding `Node("End")`.
4. Validate structure with the built-in validator:
   ```python
   errors = graph.validate()
   ```
   `validate()` checks that edge sources exist and that edge targets exist, with `"End"` allowed as a missing terminal target.
5. Export the parsed graph directly (without normalizing the graph by adding/removing nodes/edges):
   ```python
   data = graph.to_dict()     # {"nodes":[...], "edges":[...]}
   json_str = graph.to_json() # JSON string of the same structure
   ```
6. Visualize:
   ```python
   graph.visualize('dialogue_graph')            # dialogue_graph.png
   graph.visualize('dialogue_graph', format='svg')
   ```
   The built-in visualizer draws choice nodes as diamonds, line nodes as rounded boxes, and includes an `End` terminal node in the diagram.
7. Load an existing graph when needed:
   ```python
   graph = Graph.from_file('dialogue.json')
   ```

## Expected Result
- Nodes serialize as `{"id": ..., "text": ..., "speaker": ..., "type": ...}` with `type` in `{"line","choice"}`.
- Edges serialize as `{"from": ..., "to": ..., "text": ...}` where choice edges’ `text` is the option body (no `1.`/`2.` prefix), and terminal transitions can target `"End"` without requiring an `"End"` node in `nodes`.
- `graph.validate()` returns an empty list when all non-`End` edge targets exist.
