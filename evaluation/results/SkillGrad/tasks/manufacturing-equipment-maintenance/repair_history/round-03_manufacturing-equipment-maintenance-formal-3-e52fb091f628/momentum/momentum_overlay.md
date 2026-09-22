### [manufacturing-equipment-maintenance] missing required /app/output/q01.json–q05.json artifacts due to skipping pre-termination output gate
- signal: failure
- pattern: write-required-output-artifacts
- anchor: write-required-output-artifacts-do-not-end-with-empty-inventory
- gap: The run terminated (`end_turn`) without any “write outputs then validate” phase. No required `/app/output/q01.json`–`q05.json` files were created, so the grader observed an empty output inventory. The existing guidance says to treat output validation as a blocking pre-termination gate, but the executor did not execute this gate immediately before termination.
- proposed_change: Strengthen the L2 section **“Write required output artifacts (blocking pre-termination gate)”** to an explicit mandatory step list (create placeholders early → overwrite with answers → re-run validation immediately before end_turn). Optionally add a one-line reminder in **“Plan the run (contract-first)”**: “Create placeholder JSONs for all required deliverables before any analysis so missing-data cases still yield files.”

## WORKFLOW-THEMES

- (none this iteration)
