# Dialogue Script To Graph Artifacts

## Purpose
Convert a dialogue script text file into two artifacts: a JSON graph and a plain-text DOT file. The skill defines a reusable discover-parse-write-validate workflow aligned to the task's observable output contract, not a fictional library API.

## When to Use
Use when a task provides a dialogue or branching-narrative script and requires producing a serialized graph (JSON) plus a DOT representation, with reachability or schema checks. Trigger phrases: "parse the script", "dialogue graph", "emit DOT", or explicit output paths for a .json plus a .dot file.

## Procedure
- Discover inputs and outputs: list the working directory to locate the script file (do not hardcode a filename; prefer paths named in the task statement, e.g., a script.txt under /app). Confirm the exact required output paths for the JSON and DOT files from the task text.
- Define the schema explicitly before coding: nodes = [{id, text, speaker, type}] where type is one of {"line", "choice"}; edges = [{from, to, text}]. Use "from"/"to" (not source/target). Treat any referenced-but-undefined terminal id (commonly "End") as an implicit line node unless the task says otherwise.
- Implement a pure function parse_script(text: str) -> dict that: (a) splits on section headers like [SectionId]; (b) for line sections parses "Speaker: text -> Target" into a line node plus one edge; (c) for choice sections parses "N. [Tag] text -> Target" lines into a choice node plus one edge per option, preserving the full option text (including any [Tag]) in edge.text; (d) materializes any referenced target that was not explicitly declared.
- Write artifacts: dump the dict as JSON to the task-specified JSON path, and generate DOT as a Python string (header "digraph Dialogue {" plus one line per node and edge, labels quoted and escaped) written to the task-specified DOT path. Do not invoke any external graphviz binary.
- Validate before finalizing: reload the JSON file, assert required keys and edge key names, assert every edge.from and edge.to resolves to a node id, assert every node is reachable from the first declared node via BFS, and assert the DOT file is readable text beginning with "digraph". If any assertion fails, fix the parser rather than the artifact.

## Constraints / Pitfalls
- Do not import a nonexistent dialogue_graph module and do not depend on the graphviz Python package or system binary; emit DOT as a string.
- Do not rename edge keys: the contract is from/to/text; do not use source/target.
- Do not silently redirect output to alternative paths; if writing to the task-specified path fails, inspect permissions and surface the error instead of switching paths.
- Do not hardcode node ids, speakers, or option counts from any example; the parser must generalize across scripts with different sections and tags.
- Keep [Tag] prefixes inside choice edge text verbatim; do not strip or reinterpret them unless the task contract requires it.