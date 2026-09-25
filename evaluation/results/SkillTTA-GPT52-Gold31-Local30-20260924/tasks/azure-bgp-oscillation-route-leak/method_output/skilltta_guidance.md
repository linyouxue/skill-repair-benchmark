# SKILL.md

## When to use
Use this skill when you must analyze an Azure Virtual WAN–style BGP topology from multiple JSON inputs to:
1) detect **BGP route oscillation** (policy/preference cycles),  
2) detect **BGP route leaks** (violations of valley-free routing / improper re-advertisement between hubs), and  
3) evaluate a set of **candidate remediation actions** to decide whether each one resolves oscillation and/or leaks.

Before acting, gather evidence by:
- Inspecting all required JSON files under the specified input directory (confirm filenames, JSON shapes: dict vs list).
- Identifying what entities are represented (e.g., ASNs, hubs, VNets) and how edges/relationships and preferences are encoded.
- Determining how “possible solutions” are represented (structured fields vs free-text descriptions) so you can map each solution to a simulated policy/topology change without hardcoding environment-specific constants.

## Possible Failure Modes
- **Hardcoding topology facts** (specific ASNs, hub names, or directions) instead of deriving them from the input JSONs.
- **Misinterpreting oscillation**: searching only for routing loops in AS paths rather than *preference cycles* (policy oscillation requires a cycle in ranking/selection dependencies).
- **Detecting the wrong cycle**: returning any graph cycle, not the cycle relevant to routing preference dependencies that actually drives oscillation.
- **Incorrect valley-free validation**:
  - Not classifying edges correctly using relationship weights/types.
  - Missing the core leak pattern: re-advertising routes learned from one side to an inappropriate side (e.g., peer-to-peer or provider-to-provider export).
- **Solution evaluation errors**:
  - Marking a solution as resolving oscillation without actually breaking the preference cycle.
  - Marking a solution as resolving leaks without actually preventing the problematic hub-to-hub re-advertisement path.
  - Treating timing/keepalive changes as topology/policy fixes (they may affect convergence but don’t necessarily break preference cycles or export policies).
- **Output-format drift**: wrong JSON keys, wrong boolean types, non-JSON-serializable values (e.g., sets), missing required sections, or writing to the wrong path.
- **Leaking retrieved-example assumptions**: copying unrelated patterns (like “count prefixes in JSON”) as requirements or implementing irrelevant functionality.

## Possible procedures
1. **Load and normalize inputs**
   - Read JSON files from the required directory; validate successful parsing.
   - Normalize shapes: if a file may be a list of records or a dict keyed by IDs, convert to a consistent internal representation (e.g., lists of edges, dicts of attributes).
   - Extract:
     - Route advertisement data (who advertises what to whom, and via what intermediate components).
     - Routing preferences between hubs (priority/ranking data).
     - Relationship types/weights (used to label edges as customer/peer/provider or equivalent categories).
     - Candidate solutions list (ensure you can iterate deterministically across them).

2. **Construct a policy/topology graph**
   - Build a directed graph of AS-level adjacencies and/or hub connectivity as implied by the data.
   - Annotate each directed edge with relationship type for valley-free checks (derive type from the relationship-weight mapping, not from assumptions).
   - Build a preference model:
     - For each relevant decision point (e.g., hub choosing among routes), derive an ordering/score from the preferences input.
     - Represent “A is preferred over B” as a directed dependency edge in a **preference-dependency graph** (this is what you’ll cycle-detect for oscillation).

3. **Detect oscillation (preference cycle)**
   - Compute whether the preference-dependency graph contains a directed cycle.
   - If multiple cycles exist, select the one that best matches the routing decision scope (e.g., minimal/simple cycle involving the affected hubs/ASes).
   - Record:
     - `oscillation_detected` boolean.
     - `oscillation_cycle`: ordered list of ASNs/identifiers in the cycle.
     - `affected_ases`: deduplicate participants in the cycle (keep JSON-friendly list).

4. **Detect route leaks (valley-free violations / improper exports)**
   - For each advertised route or propagation chain, reconstruct the sequence of AS/hub transitions.
   - Check valley-free constraints using relationship labels:
     - Common rule-of-thumb: paths should not go “up” (customer→provider) after going “down” (provider→customer), and peer links are typically only at the top with no further “up”/“peer” afterwards.
     - Export rule-of-thumb: routes learned from a peer/provider should not be exported to another peer/provider (leak), while customer-learned routes may be exported broadly (depending on model).
   - Additionally, explicitly test the contract’s leak condition: whether one hub advertises routes to the other hub **via Virtual WAN** in a way that constitutes a leak (derive “via VWAN” from route metadata).
   - Emit `route_leak_detected` and a list of `route_leaks` entries including:
     - leaker, source, destination identifiers
     - relationship types at source/destination sides (as strings), derived from the relationship model.

5. **Evaluate candidate solutions**
   - Load `possible_solutions.json` and iterate over each solution.
   - For each solution, decide what it changes:
     - **Preference/topology changes**: would it remove or reverse at least one dependency edge in the preference graph, thereby breaking all cycles? If yes → `oscillation_resolved = true`.
     - **Advertisement/export changes**: would it prevent the hub-to-hub re-advertisement via VWAN that triggers a leak (e.g., filtering, disabling propagation, changing route export policy)? If yes → `route_leak_resolved = true`.
     - **Non-policy changes** (timers, keepalives): treat as not resolving oscillation unless the task context explicitly defines them as breaking the preference cycle; treat as not resolving leaks unless they explicitly stop the leak advertisement behavior.
   - Implement solution application as a *simulation layer*:
     - Create a modified copy of the relevant structures (preferences, export rules, adjacency) per solution.
     - Re-run the oscillation and leak detectors on the modified state.
     - Store booleans per solution in `solution_results`.

6. **Write the report**
   - Create a JSON-serializable dict matching the required schema (keys, nesting, booleans, lists).
   - Write to the exact required output path.
   - Keep ordering stable where helpful (e.g., deterministic cycle selection; stable solution iteration) to reduce evaluator brittleness.

## Verification Checklist
- [ ] All required input files were read from the specified directory; parsing errors are handled or surfaced clearly.
- [ ] The analysis derives AS/hub identifiers, relationships, and preferences **from inputs** (no hardcoded IDs/names).
- [ ] Oscillation detection is based on **preference-dependency cycles**, not merely AS-path loops.
- [ ] If `oscillation_detected` is true, `oscillation_cycle` is a valid directed cycle in the dependency graph and `affected_ases` matches its participants.
- [ ] Route leak detection includes a valley-free/export-policy rationale grounded in relationship types, and flags the specified hub-to-hub via-VWAN leak condition when present.
- [ ] Each solution is evaluated by simulating its effect and re-running detection; “resolved” is only true if the relevant condition is actually eliminated.
- [ ] Output JSON matches the required schema exactly (required keys present, correct types, lists not sets, strings where required).
- [ ] Report is saved to the exact required output path; file is valid JSON and can be re-loaded successfully.
- [ ] No content is copied from retrieved examples as requirements or facts; unrelated state/files are not modified.
