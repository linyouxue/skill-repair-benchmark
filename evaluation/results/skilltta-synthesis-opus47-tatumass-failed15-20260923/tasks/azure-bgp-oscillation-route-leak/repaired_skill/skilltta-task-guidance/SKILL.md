---
name: skilltta-task-guidance
description: Task-specific operational guidance synthesized at test time from retrieved training examples.
---

# SKILL.md

## When to use
Apply this skill when a task asks you to analyze a small network/routing topology from JSON inputs, detect specific policy violations (e.g., BGP oscillation cycles and valley-free / route-leak violations), evaluate a list of candidate remediations, and write a structured JSON report to a fixed output path.

The binding contract for the target is defined only by the task prompt: input filenames under a given data directory, the exact output path, and an output schema showing required keys (detection flags, cycle/AS lists, per-leak records with typed endpoints, and a `solution_results` map keyed by the exact solution description strings).

Before acting, gather:
- Every input JSON referenced in the prompt (routes advertised, hub-to-hub preferences, relationship-type weights, and the list of candidate solutions).
- The precise schema and key names shown in the prompt's example (do not invent new keys or rename).
- The exact criteria the prompt gives for what counts as "resolved" for each phenomenon.

## Possible Failure Modes
- Treating the example JSON in the prompt as the answer: copying its numeric ASNs, cycle members, or the sample solution string verbatim instead of computing them from the actual inputs.
- Confusing the two phenomena: reporting a cycle as a route leak, or vice versa. Oscillation = a cycle in routing/hub preferences; route leak = violation of valley-free export (e.g., a hub re-advertising routes learned from one neighbor to another neighbor when the relationship types forbid it).
- Missing that "valley-free" depends on relationship types (customer/provider/peer) loaded from the local-pref / relationship file — hardcoding rules without consulting that file.
- Emitting `solution_results` keyed by paraphrased solution text rather than the exact strings from `possible_solutions.json` (evaluators typically match on the raw string).
- Marking timer/keepalive tweaks as resolving oscillation — they don't break preference cycles. Only changes that alter the preference graph (removing an edge, reordering preferences) resolve oscillation. Only changes that stop hub-to-hub re-advertisement via Virtual WAN resolve the leak.
- Setting `oscillation_detected` or `route_leak_detected` inconsistently with the populated `oscillation_cycle` / `route_leaks` arrays (empty arrays with `true`, or non-empty with `false`).
- Writing output to the wrong directory or filename, or forgetting to create the output directory.
- Producing non-JSON-serializable values (sets, tuples, numpy ints) in the report.

## Possible procedures
1. **Load inputs defensively.** Read each JSON from the specified data directory; validate the top-level shape (dict vs list) before indexing. Build in-memory structures: an AS/hub adjacency, a preference graph (edges = "prefers over"), and a map from AS/hub to relationship types.
2. **Detect oscillation.** Construct a directed graph from the routing-preferences file and run cycle detection (e.g., DFS with a recursion stack, or `networkx.simple_cycles`). If any cycle exists, set `oscillation_detected=true`, put the cycle's AS list in `oscillation_cycle`, and union the ASes across all cycles into `affected_ases`.
3. **Detect route leaks (valley-free check).** For each advertised route, look at the ingress relationship and egress relationship using the relationship-type weights. A leak occurs when a route learned from a peer or provider is re-advertised to another peer or provider (only customer routes may be freely re-advertised). Record one entry per leak with `leaker_as`, `source_as`, `destination_as`, `source_type`, `destination_type` — using the exact keys and lowercase type strings shown in the schema.
4. **Evaluate each candidate solution independently.** For every entry in `possible_solutions.json`:
   - `oscillation_resolved`: true only if the change removes at least one edge from every detected preference cycle (e.g., reorders/removes a hub preference).
   - `route_leak_resolved`: true only if the change stops the offending hub from re-advertising routes across Virtual WAN to the other hub (e.g., disables inter-hub propagation, filters exports).
   - Timer/keepalive/holdtime changes: neither resolves oscillation nor a valley-free leak on their own.
   - Key each result by the solution's exact description string.
5. **Assemble and write the report.** Match the schema keys exactly, ensure booleans and lists are consistent, `os.makedirs` the output directory, and `json.dump` with a stable indent. Convert any sets to sorted lists.

Decision points:
- If no cycle: `oscillation_detected=false`, `oscillation_cycle=[]`, `affected_ases=[]`.
- If no leak: `route_leak_detected=false`, `route_leaks=[]`.
- Still emit `solution_results` for every provided solution regardless of whether issues were detected (both sub-flags can be `false` if nothing to resolve or the fix is irrelevant — follow the prompt's definition literally).

## Verification Checklist
- [ ] All input files listed in the prompt were opened from the correct data directory; none were assumed.
- [ ] Output written to the exact path specified in the prompt (`/app/output/oscillation_report.json` per the target contract), with the directory created if missing.
- [ ] JSON top-level keys match the schema exactly: `oscillation_detected`, `oscillation_cycle`, `affected_ases`, `route_leak_detected`, `route_leaks`, `solution_results`.
- [ ] Each element in `route_leaks` has all five fields with correct types; `source_type`/`destination_type` values come from the relationship data, not guessed.
- [ ] `solution_results` contains one entry per solution in `possible_solutions.json`, keyed by the raw description string (not paraphrased), each with both `oscillation_resolved` and `route_leak_resolved` booleans.
- [ ] Detection booleans are consistent with their corresponding arrays (empty ⇔ false).
- [ ] No values, ASNs, cycles, or solution strings were copied from the prompt's illustrative example or from retrieved examples; all are derived from the actual inputs.
- [ ] Output is valid JSON (no sets, tuples, or numpy scalars); re-load it with `json.load` to confirm.
- [ ] Recovery: if a file is malformed or a key is missing, fail loudly with a clear message rather than silently emitting a partial report.
