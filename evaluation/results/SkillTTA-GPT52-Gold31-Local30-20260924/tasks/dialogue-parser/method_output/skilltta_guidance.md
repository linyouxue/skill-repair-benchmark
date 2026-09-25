# SKILL.md

## When to use
Use this skill when you must implement a text-to-graph parser that:
- Reads a dialogue/script plaintext file with section headers and dialogue/choice lines.
- Produces a structured JSON graph (nodes + edges) and a DOT visualization file.
- Exposes a required pure function (e.g., `parse_script(text: str)`) that returns the parsed graph object for downstream validation.

Before acting, gather evidence from the task context about:
- The exact input syntax patterns (section headers, speaker lines, choices, arrow `->` transitions, optional tags like `[Tag]`).
- The required JSON schema (node fields, edge fields, allowed node `type`s).
- Graph constraints enforced by evaluator (reachability from first node, edge targets must exist except allowed terminal behavior, special terminal nodes such as `"End"` may be shared).

## Possible Failure Modes
- **Wrong JSON shape**: returning a dict that lacks top-level `nodes`/`edges`, or node/edge entries missing required keys (`id`, `text`, `speaker`, `type`; `from`, `to`, `text`).
- **Inconsistent IDs**: duplicate node IDs, non-deterministic IDs across runs, or IDs that don’t match edge endpoints.
- **Unreachable nodes**: parsing all sections into nodes but failing to link them so some nodes cannot be reached from the first node.
- **Dangling edge targets**: edges referencing section/node IDs that were never created; forgetting the “exception” rule for terminal/last node behavior.
- **Mis-parsing line types**: treating choice lines as normal dialogue lines (or vice versa), dropping the choice label text, or losing speaker attribution.
- **Incorrect handling of blank lines / whitespace**: extra empty nodes, merged lines, or missing transitions due to untrimmed spaces around `->`.
- **Losing bracketed tags**: stripping `[Lie]` / `[Attack]`-like prefixes incorrectly (either removing meaningful text or failing to keep consistent choice text).
- **DOT file invalid**: generating DOT that doesn’t quote IDs with special characters, omits edges, or fails to render due to unescaped quotes/newlines.
- **Validation gaps**: not checking constraints before writing output, causing late failures in hidden tests.

## Possible procedures
1. **Define a robust parsing model**
   - Decide node categories based on the contract (e.g., `"line"` and `"choice"`).
   - Decide how section headers map to graph structure (commonly: a section is an entry point; its first content becomes the section’s first node, and incoming edges target that node or the section ID resolved to that node).
   - Ensure node IDs are unique and stable. Common approaches:
     - Use section name + incremental counter within section.
     - Maintain an internal counter and a mapping from logical anchors (section names) to actual node IDs.

2. **Tokenize the input safely**
   - Split into lines; preserve order.
   - Normalize whitespace: trim line ends; skip purely empty lines.
   - Detect section headers (e.g., `[...]` on its own line) and start a new section context.

3. **Parse content lines within a section**
   - For each non-header line, classify:
     - **Dialogue line**: typically `Speaker: text -> Target` (target may be optional depending on contract).
     - **Choice line**: typically `N. text -> Target`.
   - Extract:
     - `speaker` (empty or `null` for choices unless specified otherwise by the contract).
     - `text` (retain meaningful markers like bracketed tags unless the contract says to strip).
     - `to` target after `->` (trim whitespace). If no `->`, treat as terminal within the section or apply contract rules.

4. **Build nodes and edges incrementally**
   - Create a node for each parsed line/choice, with required fields filled.
   - Create edges:
     - From a node to its explicit `-> Target` destination (store `edge.text` as the label that triggered the transition; for dialogue lines this may be empty or the line text depending on contract—choose consistently and document).
     - Optionally, chain implicit flow within a section if the input format implies sequential execution (only if consistent with the contract and tests).
   - Maintain a mapping for destinations:
     - If destinations refer to section names, resolve them to the entry node of that section once known.
     - If a destination node/section is referenced before it is defined, store a deferred edge and resolve in a second pass.

5. **Second pass: resolve references and enforce constraints**
   - Resolve all deferred edges to actual node IDs.
   - Enforce the evaluator-visible constraints:
     - **All nodes reachable from first node**: run a graph traversal from the first node ID; if unreachable nodes exist, either connect them appropriately (if justified by the script structure) or omit them if they are truly unreachable and the contract allows omission.
     - **Edge targets must exist**: verify every `edge.to` is a known node ID, except any contract-allowed terminal exception (handle explicitly rather than implicitly).
     - **Shared terminal nodes**: if a canonical terminal node like `"End"` is expected, ensure multiple edges can point to the same node without duplicating it.

6. **Write outputs deterministically**
   - JSON: write `{ "nodes": [...], "edges": [...] }` with consistent ordering (e.g., creation order) and stable IDs.
   - DOT:
     - Emit `digraph` with node declarations (optional) and edge statements.
     - Quote node IDs and labels; escape quotes/newlines.
   - Implement the required `parse_script(text)` as the single source of truth; file I/O should call this function and then serialize.

7. **Add minimal defensive checks (inspired by common benchmark patterns)**
   - Handle missing/empty input gracefully (either raise clear errors if allowed, or return an empty graph if specified).
   - Validate graph object types before serialization (lists/dicts, required keys) to avoid writing malformed JSON.

## Verification Checklist
- [ ] `parse_script(text: str)` exists, is callable, and returns a Python dict/object representing the full graph.
- [ ] Returned object matches required schema: top-level `nodes` and `edges`; each node has `id`, `text`, `speaker`, `type`; each edge has `from`, `to`, `text`.
- [ ] Node IDs are unique and every `edge.from` refers to an existing node.
- [ ] Every `edge.to` refers to an existing node **except only** where the task contract explicitly allows a terminal/last-node exception.
- [ ] Graph reachability: a traversal from the first node reaches every node in `nodes`.
- [ ] Multiple incoming edges to a shared terminal node (e.g., `"End"`) work without duplication or conflicts (if such a node is part of the contract/tests).
- [ ] JSON output file and DOT output file are produced at the required paths, with valid syntax (JSON parses; DOT renders/has correct quoting).
- [ ] No concrete IDs/paths/names from retrieved examples were copied into logic as “requirements”; only reusable patterns (validation, robust parsing) were applied.
- [ ] Re-run after a small input perturbation (extra blank lines, extra spaces around `->`) to confirm parsing is stable and constraints still pass.
