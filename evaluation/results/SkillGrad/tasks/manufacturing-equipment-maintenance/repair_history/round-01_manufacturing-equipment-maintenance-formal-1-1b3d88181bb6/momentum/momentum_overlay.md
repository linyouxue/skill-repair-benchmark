### [manufacturing-equipment-maintenance] missing /app/output/*.json deliverables (empty output inventory)
- signal: failure
- pattern: write-required-output-artifacts | new
- anchor: (none)
- gap: Agent terminated (termination_reason: end_turn) while the output inventory is empty ([]), meaning none of the required JSON artifacts (e.g., /app/output/q01.json … q05.json) were written. The current skill content focuses on domain computations (ramps, TAL, peaks, sorting by time, etc.) but does not enforce a deterministic “materialize deliverables + existence/schema verification” completion protocol.
- proposed_change: Add an L2 section to SKILL.md (new anchor, e.g., write-required-output-artifacts) that: (1) enumerates required filenames/paths, (2) mandates writing each JSON to /app/output/, (3) requires a pre-termination checklist verifying files exist and JSON parses and matches required schema/formatting, and (4) specifies what to output when data is missing (still write files with nulls/empty arrays per spec).

## WORKFLOW-THEMES

- (none this iteration)
