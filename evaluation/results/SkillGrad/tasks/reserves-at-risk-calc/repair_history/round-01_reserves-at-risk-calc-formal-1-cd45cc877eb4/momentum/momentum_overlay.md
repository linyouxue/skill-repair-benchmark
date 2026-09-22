### [reserves-at-risk-calc] missing output workbook artifact due to skipped save/export step
- signal: failure
- pattern: save-and-verify-output-artifact
- anchor: (none)
- gap: The run terminated at finalization without performing the required “Save As / export workbook to the specified output path” step, so the output inventory was empty. There is no enforced end-of-task persistence check (save to exact path/filename) followed by an existence/confirmation step (e.g., verify file exists in output directory or re-open).
- proposed_change: Add an L2 hard requirement checklist section for all spreadsheet tasks: before ending, always (1) save/export to the exact required output path and filename, (2) immediately verify the file exists at that path (and optionally re-open), and (3) only then terminate. If verification fails, retry saving with corrected path until it passes.

## WORKFLOW-THEMES

- (none this iteration)
