# Dialogue Script To Graph

## Purpose
Convert a dialogue script into a graph artifact pair: a JSON file describing nodes and edges, and a DOT file describing the same graph for visualization. The skill defines the schema, the parsing workflow, and the post-write validation.

## When to Use
Use when a task asks to parse a dialogue or branching-narrative script into structured graph data with both a JSON serialization and a DOT representation, typically by implementing a `parse_script` function in a specified solution module. Do not use for pure text summarization, rendering PNG/SVG diagrams, or tasks that supply a prebuilt graph library.

## Procedure
- Discover the environment: locate the input script path and the required output paths (JSON and DOT) from the task description or working directory listing. Do not hard-code paths.
- Read the task spec and record the exact schema: node fields (commonly `id`, `text`, `speaker`, `type` with `type` in {`line`, `choice`}), edge fields (commonly `from`, `to`, `text`), top-level JSON shape (`{"nodes": [...], "edges": [...]}`), and any terminal sentinel (e.g., implicit `End`) that may appear as an edge target without a materialized node.
- Implement `parse_script(text)` to iterate sections, emit one node per labeled block, create `choice`-type hub nodes where multiple branches exist, and connect them with edges. Strip tag prefixes like `[Lie]` or `[Attack]` from choice edge labels only if the task requires normalized text; otherwise preserve them.
- Serialize: write JSON via `json.dump` to the declared JSON path; build the DOT string manually (`digraph G { ... }`) and write it to the declared DOT path. Do not invoke external graphviz binaries.
- Validate post-write: reload the JSON, assert required keys and types, assert every edge `to` resolves to a node id or the allowed terminal sentinel, and assert reachability from the first section. Confirm the DOT file exists and begins with `digraph`. Print a brief "schema OK" line.

## Constraints / Pitfalls
- Never import a nonexistent helper library; implement parsing in standard Python.
- Field names come from the task, not from this skill; if the task uses `from`/`to`, do not emit `source`/`target` (or vice versa).
- Distinguish verifier-allowed edge targets (terminal sentinels) from nodes that must be materialized; encode the distinction in the post-write check.
- Keep choice hubs explicit: a branching point is a `choice` node with outgoing edges carrying the option text, not inline edge metadata on a `line` node.
- If the DOT or JSON path is unspecified, fail loudly rather than guessing a path.