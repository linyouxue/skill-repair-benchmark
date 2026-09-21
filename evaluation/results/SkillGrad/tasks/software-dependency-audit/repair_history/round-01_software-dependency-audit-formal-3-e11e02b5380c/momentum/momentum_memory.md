### write-and-verify-required-deliverable | workflow | ensure required CSV artifact is written to the exact path and verified before termination
- anchor: (none yet)
- appeared_in: iter_0
- description: The executor reaches end-of-run without producing the externally graded deliverable (here: a CSV file at an exact required path). This is a workflow/completion failure: analysis may be correct or partially complete, but no artifact exists for the grader to inspect (e.g., output inventory shows []). The key mechanism is missing a hard “write → check exists → check schema/non-emptiness” checkpoint.
- latest_executor_action: Maintain a completion checklist for artifact-based tasks. Before terminating: (1) write the deliverable to the exact required path (not a relative or alternate location), (2) verify it exists and is non-empty (or header-only when appropriate), and (3) verify format invariants (expected header columns; at least one data row when findings exist). Only then end the run.
- remedy_log:
  - iter_0 | diagnosis: terminated without creating `/root/security_audit.csv` (output inventory `[]`)
            | patch: (none yet — initial record created from diagnosis)
