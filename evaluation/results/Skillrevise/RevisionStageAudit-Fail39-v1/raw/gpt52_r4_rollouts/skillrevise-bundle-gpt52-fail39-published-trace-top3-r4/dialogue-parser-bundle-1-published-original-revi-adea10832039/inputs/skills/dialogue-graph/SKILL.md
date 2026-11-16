# Dialogue Script -> Graph Artifacts (JSON + DOT)

## Purpose
Convert a plain-text dialogue script into a validated dialogue graph representation (nodes + edges) and serialize it into verifier-checked artifacts (typically JSON and DOT text), using environment discovery and post-write schema/consistency checks.

## When to Use
Use this when a task requires parsing a dialogue script format (often sectioned and/or choice-based) into a machine-validated graph schema and emitting artifacts that downstream tooling/tests verify (for example, a JSON graph and a .dot file).

## Procedure
- 1) Discover the contract and environment before coding anything irreversible.
- Locate the repository entrypoint(s) and expected outputs by searching for any of: README/spec, tests, verify scripts, fixture examples, or schema definitions.
- Identify (a) required artifact types (JSON, DOT, other), (b) exact key names (for example "from" vs "source"), (c) start-node rule (first section vs a sentinel name), and (d) terminal-node convention (whether a sentinel like "End" is allowed or must be materialized).
- Execution anchor: run the available verification command (tests or a provided checker) to see explicit failures and expected formats.
- 2) Parse the script into an internal, contract-shaped graph model.
- Read the script as text; normalize line endings; ignore empty/comment-only lines if the spec allows.
- Discover sections (for example bracketed headers) rather than assuming a fixed start label; set start_id to the first section encountered unless the contract says otherwise.
- For each section, classify content into node types required by the contract (for example "line" vs "choice") using only rules supported by the spec/tests; if ambiguous, choose a deterministic rule and record/raise a parse error when the contract requires strictness.
- Extract fields (speaker/text/choice text/targets) exactly as the contract names them; do not invent extra fields.
- 3) Build edges with strict referential rules and deterministic ID handling.
- Create node ids from section identifiers exactly as parsed (preserve case/spacing rules per contract).
- Create edges only when the script indicates a transition (for example an arrow); store edge endpoints using the contract keys ("from"/"to" or "source"/"target").
- Decision point: if an edge target is referenced but no section defines it:
- If the contract explicitly allows a terminal/sentinel target, handle it exactly as required (either permit as an edge to a non-materialized sentinel, or materialize a terminal node). Do not guess.
- Otherwise, fail validation (do not silently auto-create nodes).
- 4) Serialize artifacts to verifier-visible files using discovered paths/names.
- Write JSON using the exact schema and key ordering only if required (otherwise any ordering).
- Write DOT as plain text (no external graphviz install, no image generation). Keep it minimal: declare a directed/undirected graph per contract and emit node/edge statements using node ids safely escaped if needed by DOT syntax.
- If output paths are not provided, discover the expected location from tests/spec; do not hard-code project-specific paths.
- 5) Validate before finalizing (reload-and-assert).
- Reload the written JSON from disk and assert:
- Top-level object has required keys (for example nodes, edges) and correct types (lists/objects).
- Each node has required fields (at least id and type) and unique ids.
- Each edge has required fields and references valid node ids, except only those terminal conventions explicitly allowed by the contract.
- If reachability is required, compute reachability from start_id and assert all required nodes are reachable.
- Read the DOT file back as text and sanity-check it matches the contract (for example starts with "digraph" if directed) and references known node ids/edges.

## Constraints / Pitfalls
- Do not assume any specific library/module (for example a pre-existing Graph/Node/Edge package) exists; always discover what is available in the environment and implement with standard language features unless verified otherwise.
- Do not assume a fixed start node label (for example "[Start]") or silently auto-create missing targets; derive start/terminal behavior from the observable contract (spec/tests) and enforce it with a post-write reload-and-assert check.