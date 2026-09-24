---
name: dialogue-graph
description: Build, validate, serialize, and visualize a dialogue graph parsed from
  a bracketed-section script into `{"nodes":[...],"edges":[...]}` plus a `.dot` graph.
---

## Steps
1. Inspect the script structure as **sections** starting with headers like `[SectionId]`, collecting each section’s non-empty lines until the next header.
2. Confirm each section is **one of**:
   - a single **speaker line**: `Speaker: text. -> TargetId`
   - a **choice hub**: multiple numbered lines like `1. Choice text -> TargetId`  
   (No mixing speaker+choices in the same section; no “nonconforming” lines.)
3. Parse sections into nodes:
   - For a speaker line section, create a node `{id: SectionId, type:"line", speaker:<Speaker>, text:<text>}`.
   - For a choice section, create a node `{id: SectionId, type:"choice", speaker:"", text:""}` (or a minimal placeholder text if needed).
4. Parse transitions into edges:
   - From a speaker line section: add one edge `{"from": SectionId, "to": TargetId, "text": ""}`.
   - From a choice section: for each choice, add `{"from": SectionId, "to": TargetId, "text": <full choice label/text>}`.
5. Ensure all edge targets exist by creating missing target nodes when needed; if the script references `End` without defining `[End]`, add an implicit `End` node (commonly `{id:"End", type:"line", speaker:"", text:""}`).
6. Validate graph constraints:
   - Determine the **start node** as the first section encountered in the file.
   - Run reachability (BFS/DFS) from the start node; error if any node is unreachable.
   - Error on missing edge targets **other than** the allowed implicit end case (or create the missing nodes as in Step 5).
7. Serialize outputs:
   - Write JSON as `{"nodes":[{"id","text","speaker","type"}...],"edges":[{"from","to","text"}...]}`.
   - Write a `.dot` file with nodes and directed edges for visualization (choice nodes can be `shape=diamond`, line nodes `shape=box`).
8. When searching the script from the shell for patterns starting with `-` (e.g., `-> End`), use `grep` with `--` to stop option parsing:  
   `grep -n -- '-> End' /app/script.txt`
9. When using a terminal tool that only accepts one command at a time, run commands in separate calls, or chain within a single command using `&&` (not as two separate lines).
## Expected Result
A parsed dialogue graph where every node is reachable from the first section, all referenced targets exist (with an implicit `End` node if needed), and the graph is exported to valid `dialogue.json` plus a readable `dialogue.dot`.
