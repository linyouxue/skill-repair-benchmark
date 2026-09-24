### [energy-market-pricing] missing required output file (`report.json` not written)
- signal: failure
- pattern: deliverable-commit-phase
- anchor: (none)
- gap: The run terminated without writing the required deliverable artifact; the diagnosis notes the output inventory is empty and `report.json` was not created. There is no enforced final “write + verify deliverables” step, and no fallback behavior to emit a structured error report when upstream computation fails.
- proposed_change: Add an explicit end-of-procedure deliverable commit step to the relevant L2 workflow (likely in the top-level task skill, or a shared “finalize outputs” section): always write `report.json` with the exact expected schema, then immediately validate by reopening/parsing it (or `ls` + `python -c 'json.load(...)'`). If an exception occurs earlier, catch it and still write `report.json` containing an `error` object (message, traceback summary) so the harness never receives an empty output.

## WORKFLOW-THEMES

- (none this iteration)
