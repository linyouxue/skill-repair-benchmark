# BGP Oscillation and Route Leak Diagnosis and Solution Classification

## Purpose
Diagnose BGP oscillation (preference cycles) and route leaks (valley-free export violations) from provided topology/policy evidence, then classify candidate mitigations by whether they resolve the defined control-plane problem (break cycles and/or prevent forbidden exports), using discovery and schema validation rather than hard-coded files or vendor assumptions.

## When to Use
Use this skill when a task provides (or implies) JSON artifacts describing a BGP-like topology, routing preferences/local preference, route propagation events, and/or a list of candidate solutions that must be judged against formal definitions of "oscillation" and "route leak" in that environment.

## Procedure
- 1) Discover inputs (do this before reasoning)
- List available files in the task data/work directory and collect all readable *.json.
- Parse each JSON safely (fail closed on parse errors) and build an inventory:
- Possible topology keys: edges, links, neighbors, adjacencies.
- Possible preference keys: preferences, preferred_next_hop, best_path.
- Possible relationship keys: relationships, provider/customer/peer labels.
- Possible local-pref keys: local_pref, weights, rankings.
- Possible route evidence keys: route, prefix, origin, events, announcements.
- Possible candidates keys: solutions, possible_solutions, candidates.
- Checkpoint: produce an internal map "role -> filename(s)" and do not assume any specific filename.
- 2) Validate minimal schemas and choose fallbacks (gate before analysis)
- Required for oscillation detection: a preference mapping (node -> preferred neighbor) OR enough local-pref data plus adjacency to derive a deterministic best neighbor.
- Required for leak detection: relationship labels per directed edge OR event evidence that explicitly states learned-from and advertised-to for a route.
- If a required role is missing:
- If an alternate can be derived (e.g., local_pref + adjacency to choose best), do so and record the derivation rule.
- Otherwise stop classification and return "insufficient information" for the missing dimension, naming exactly what is needed (do not guess).
- Checkpoint: assert the set of nodes referenced across files is consistent; if not, restrict to the intersection and record the mismatch.
- 3) Detect oscillation via preference-cycle analysis
- Build a directed graph Gpref where each node points to its currently preferred next hop (from preferences or derived best).
- Run cycle detection (any directed cycle is sufficient evidence of potential oscillation under BGP-like path selection).
- Output evidence in reusable form: "cycle found: [n1, n2, ...]" or "no cycle found in Gpref".
- Decision point: if no cycle is found, do not claim oscillation; proceed to leak analysis and solution classification only for leaks or other required labels.
- 4) Detect route leaks via valley-free violation (choose the evidence source)
- If explicit relationships exist (provider/customer/peer):
- Apply valley-free export rule: routes learned from a peer or provider must not be exported to a peer or provider (only to customers).
- Determine if any observed or implied export violates this rule.
- Else if route events exist (learned_from, advertised_to, path):
- Infer "learned-from class" and "advertised-to class" only if the event schema provides it; otherwise do not invent relationships.
- Mark leak when an event explicitly shows peer/provider-learned routes exported to peer/provider.
- Output evidence: a minimal set of violating (learned_from, exporter, advertised_to, route/prefix) tuples, or "no violations found with available evidence".
- 5) Classify candidate solutions by modeled effect (not keywords)
- For each candidate, first map it to an abstract operation type, using only what the candidate explicitly states:
- Preference change: modifies local-pref/selection so the preferred-next-hop edges change.
- Export filter/policy: blocks advertising certain learned routes to certain neighbors.
- Import filter/validation: rejects receiving certain routes (may help, but does not directly stop exporting leaks unless specified).
- Forwarding override (static routes/intent/UDR): changes forwarding without changing BGP control-plane behavior.
- Topology removal (disable session/shut link): removes an adjacency.
- Unclear: cannot be mapped without extra details.
- Then decide resolution against the task-defined problems:
- Resolves oscillation iff the operation guarantees removal of all directed cycles in Gpref (or prevents the cyclic dependencies by removing at least one required preference edge via filtering), based on the discovered topology/prefs.
- Resolves leak iff the operation enforces valley-free exports on all relevant edges (e.g., export filters that stop peer/provider-learned routes from reaching peers/providers).
- Forwarding-only overrides: mark as "does not resolve control-plane oscillation/leak" unless the task explicitly defines resolution in terms of forwarding outcome.
- If mapping or effect cannot be determined from available inputs, return "unknown" with the exact missing detail needed (e.g., which edges are filtered, which direction, which route class).

## Constraints / Pitfalls
- Do not hard-code file names, ASNs, cloud products, or vendor operational constraints unless they are explicitly present in the task inputs or stated in the task contract.
- Do not use string/keyword heuristics as the primary classifier; classification must be justified by a modeled effect on (a) the preference-cycle graph and/or (b) valley-free export constraints, otherwise return "unknown/needs-clarification."