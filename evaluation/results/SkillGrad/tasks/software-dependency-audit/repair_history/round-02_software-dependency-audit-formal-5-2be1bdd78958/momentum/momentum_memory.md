### write-and-verify-required-deliverable | workflow | ensure required CSV artifact is written to the exact path and verified before termination
- anchor: complete-the-deliverable-workflow
- appeared_in: iter_0, iter_3
- description: The executor reaches end-of-run without producing the externally graded deliverable (here: a CSV file at an exact required path). This is a workflow/completion failure: analysis may be correct or partially complete, but no artifact exists for the grader to inspect (e.g., output inventory shows []). The key mechanism is missing a hard “write → check exists → check schema/rowcount” checkpoint, and/or treating the output path as optional rather than part of the task spec.
- latest_executor_action: Maintain a completion checklist for artifact-based tasks. Identify the deliverable path(s) up front and treat them as part of the spec. Before terminating: (1) write the deliverable to the exact required path (not a relative or alternate location), (2) verify it exists at that path, and (3) verify format invariants (expected header columns; row count matches expectation—header-only when there are zero findings, otherwise ≥1 data row). Only then end the run.
- remedy_log:
  - iter_0 | diagnosis: terminated without creating `/root/security_audit.csv` (output inventory `[]`)
            | patch: (none yet — initial record created from diagnosis)
  - iter_3 | diagnosis: terminated without producing required deliverable `/root/security_audit.csv` despite skill rule requiring write + hard verification gate
            | patch: (none yet — record/anchor updated from evolved skill alignment)
