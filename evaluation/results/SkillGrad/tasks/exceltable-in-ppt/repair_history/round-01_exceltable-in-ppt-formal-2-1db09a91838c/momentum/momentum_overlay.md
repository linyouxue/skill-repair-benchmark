### [exceltable-in-ppt] Missing/empty trace and inaccessible artifacts block diagnosis
- signal: failure
- pattern: harness-artifact-availability
- anchor: (none)
- gap: No actionable execution evidence is available: the trajectory trace file is empty and other required artifacts (skill files/verifier evidence/result.json) are missing or inaccessible within the allowed project root. The failure occurs before any inspectable agent decision.
- proposed_change: Treat as harness/environment fix rather than a skill edit. Ensure the run exports trace.jsonl and all outputs/evidence into the permitted sandbox root, and use consistent in-root paths so the diagnoser can read them.

## WORKFLOW-THEMES

- (none this iteration)
