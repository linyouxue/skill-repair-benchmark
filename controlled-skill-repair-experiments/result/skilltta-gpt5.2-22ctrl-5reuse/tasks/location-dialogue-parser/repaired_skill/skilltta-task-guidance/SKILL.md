---
name: skilltta-task-guidance
---

# SkillTTA Task Guidance: Dialogue Script → JSON Graph (+ DOT)

## Goal
Implement a parser that converts a dialogue script text into a graph:

```json
{
  "nodes": [{"id":"", "text":"", "speaker":"", "type":""}],
  "edges": [{"from":"", "to":"", "text":""}]
}
```

and also exports a Graphviz `.dot` visualization.

Key constraints to satisfy:
1. **All nodes must be reachable from the first node** (start node).
2. **All edge targets must exist** (create missing target nodes when referenced), except there should be **no “dangling edge”**; “last node” means “node with no outgoing edges”, not “edge to missing node”.
3. **Multiple paths can lead to a node `End`**; `End` should exist as a node when referenced.

---

## Input Format (Expected Patterns)
The script is organized into **sections**:

- Section header: `[SectionId]`
- Dialogue line:
  - `Speaker: text` optionally followed by `-> TargetSection`
- Choice lines (numbered):
  - `1. option text -> TargetSection`
  - Option text may include tags like `[Lie]` or `[Attack]`.

Blank lines may appear between items.

---

## Parsing Strategy
### 1) Split into sections
Scan line-by-line:
- When encountering `^[\[](.+)[\]]$`, start a new current section.
- Collect subsequent non-header lines as that section’s body.

Store an ordered list of section ids to determine the **start node** = first section encountered.

### 2) Decide node type per section
Common practical convention for validation:
- If a section contains any numbered choice lines (`^\d+\.`), create a **single node** of type `"choice"` with `id = section_id`.
- Else, create a node of type `"line"` with `id = section_id`.

### 3) Parse node fields
- **Line node**:
  - Parse first non-empty line like `Speaker: text (-> target optional)`.
  - `speaker` = parsed speaker, else empty string.
  - `text` = dialogue text without the `-> Target` suffix.

- **Choice node**:
  - `speaker` = `""` (or a stable sentinel like `""`).
  - `text` = either empty or a short prompt like `"Choose:"` (keep stable; do not inject extra options into node text if edges carry option text).

---

## Adding Edges (Critical)
### A) Dialogue line edges
For a line node, if its line contains `-> Target`:
- Add edge:
  - `from = current_section_id`
  - `to = Target`
  - `text = ""` (or `null` but prefer empty string for schema stability)

### B) Choice option edges
For each numbered choice line:
- Extract option label text and its target:
  - Example: `3. [Lie] I'm a merchant... -> MerchantPath`
  - Edge:
    - `from = current_section_id`
    - `to = MerchantPath`
    - `text = "[Lie] I'm a merchant..."` (option text only; do not include the leading `3.`)

### C) Ensure all edge targets exist
When an edge references `to = X`:
- If node `X` does not exist yet, **create a placeholder node** immediately.
  - Recommended placeholder:
    - `id = X`
    - `type = "line"`
    - `speaker = ""`
    - `text = ""`
- If later you parse a real section `[X]`, overwrite/upgrade the placeholder.

This avoids invalid graphs where edges point to missing nodes.

---

## End Node Convention
Treat `End` specially to satisfy “multiple paths can lead to End”:
- If any edge target is exactly `"End"` and `[End]` is not present, create node:
  - `id = "End"`
  - `type = "line"`
  - `speaker = ""`
  - `text = "End"` (or empty; but setting text to `End` is clearer)
- `End` typically has **no outgoing edges**.

Do **not** allow edges to a non-existent end state; always materialize `End` as a node when referenced.

---

## Reachability Constraint
After building nodes/edges:
1. Identify `start_id` = first section header encountered.
2. Run BFS/DFS from `start_id` following edges.
3. If unreachable nodes exist:
   - Preferred: **drop unreachable placeholder nodes** created only by bad targets (but only if they are truly unreachable).
   - If unreachable nodes are real sections, you may either:
     - connect them (not recommended unless spec says so), or
     - remove them to satisfy validation.

In most dialogue scripts, unreachable nodes are accidental; removing them is the safest way to satisfy constraint (1).

---

## Export (JSON + DOT)
### JSON Export
Write `/app/dialogue.json` as:
- UTF-8
- `indent=2`
- Ensure output is an object with `nodes` and `edges` lists.

Before writing:
- Validate types:
  - `nodes` is list of dicts
  - `edges` is list of dicts
  - Each node has `id,text,speaker,type`
  - Each edge has `from,to,text`

### DOT Export
Write `/app/dialogue.dot` in Graphviz format:
- Emit:
  - `digraph Dialogue { ... }`
  - Node labels: include speaker/text succinctly, e.g.
    - `GateScene [label="GateScene\nGuard: Halt!...", shape=box]`
    - `NameChoice [label="NameChoice\n(choice)", shape=diamond]`
  - Edge labels:
    - For choice edges: label is option text
    - For line edges: label can be empty

Remember to escape quotes and newlines in DOT labels.

---

## Practical Implementation Notes
- Keep a `nodes_by_id: dict[str, dict]` to deduplicate nodes.
- Keep `edges: list[dict]` and append in parse order.
- When upgrading a placeholder node, preserve its `id` and overwrite `type/speaker/text` with parsed content.
- Robust parsing:
  - Strip whitespace.
  - Ignore empty/comment lines.
  - Parse arrows with a right-split on `->` to avoid breaking text containing `->` earlier.

---

## Minimal Validation Checklist
Before finalizing:
- `start_id` exists in nodes.
- For every edge, `from` and `to` exist in nodes.
- All nodes reachable from `start_id`.
- `End` node exists if referenced.

---
