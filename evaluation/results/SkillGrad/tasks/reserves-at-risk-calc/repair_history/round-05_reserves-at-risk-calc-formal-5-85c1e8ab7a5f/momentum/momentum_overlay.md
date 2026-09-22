### [reserves-at-risk-calc] required output workbook not produced at mandated path
- signal: failure
- pattern: save-and-verify-output-artifact
- anchor: workflow-deliver-the-required-artifact-mandatory
- gap: The run ended with the workbook saved/left at `data/test-rar.xlsx` while the required deliverable `/root/output/rar_result.xlsx` was never written. The executor did not apply the L2 completion gate steps: explicit Save As/export to the *exact absolute* required path, followed immediately by an existence check at that path before terminating.
- proposed_change: Strengthen/operationalize the L2 “Workflow: Deliver the required artifact (mandatory)” section so it behaves like a hard stop: add a minimal retry loop/checklist the executor must run at end-of-run—(a) restate required absolute path string, (b) `mkdir -p` parent dir, (c) save-as to that exact path, (d) `Path.exists()` assert, (e) if missing/mismatch, do not end; correct and repeat. Consider adding an explicit anti-pattern callout: “Do not leave final output in `data/` or other workspace-relative paths; that is always a failure unless explicitly required.”

## WORKFLOW-THEMES

- (none this iteration)
