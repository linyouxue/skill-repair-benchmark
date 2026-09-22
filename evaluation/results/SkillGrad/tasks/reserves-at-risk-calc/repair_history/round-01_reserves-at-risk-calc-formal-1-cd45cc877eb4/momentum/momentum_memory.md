### save-and-verify-output-artifact | workflow | executor ends run without saving required workbook to specified output path
- anchor: (none yet)
- appeared_in: iter_0
- description: For spreadsheet tasks, the executor may complete analysis or edits in-memory but terminate without persisting the required artifact (e.g., an .xlsx workbook) to the exact output path/filename demanded by the task. This produces an empty output inventory and fails the task at the first externally observable checkpoint. The mechanism is a missing end-of-run “persistence + existence verification” step (Save/Export, then confirm file presence or re-open).
- latest_executor_action: Treat saving as a hard requirement gated by a completion checklist. Before ending: (1) write/save the workbook to the exact required output path and filename, (2) verify persistence by checking the file exists at that path (and ideally re-open to confirm), and (3) only then terminate. If save fails or path mismatches, retry with corrected path until verification passes.
- remedy_log:
  - iter_0 | diagnosis: run produced no output file; agent terminated without executing/finishing “Save As/export workbook to required path”
            | patch: (none yet; record created from diagnosis)
