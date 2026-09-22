# Pattern record (iteration 3)

### deliverable-writeback-and-final-existence-check | workflow | completes edits but fails to persist/emit the required final artifact
- anchor: confirm-sandboxed-artifact-i-o-before-operating
- appeared_in: iter_2, iter_3
- description: The executor performs (or plans) in-memory / intermediate edits but ends the run without producing the harness-required deliverable file at the specified path. In this batch, the failure mode is specific to PPTX containing an embedded Excel (OLE) object: after extracting and editing the embedded workbook, the agent does not re-embed/replace the updated package back into the PPTX and does not save the resulting presentation to `/root/results.pptx`. The earliest external symptom is that the output inventory contains only the original `input.pptx`, and the run terminates (`end_turn`) without a pack/save writeback step.
- latest_executor_action: Treat “writeback” as a first-class, end-to-end pipeline requirement. For PPTX+embedded-XLSX tasks: (1) extract the embedded workbook, (2) apply the minimal intended cell edits while preserving formulas/formatting, (3) write the workbook back into the embedded part/OLE package, (4) pack/save a new PPTX to the exact required output path, and (5) before terminating, assert the output file exists and is non-empty. If the existence check fails, do not end the turn—perform the missing pack/save step and re-check. (Optional but helpful: `ls -l` the output directory immediately before ending to ensure the harness will collect the file you wrote.)
- remedy_log:
  - iter_2 | diagnosis: no updated output presentation was produced; agent skipped re-embed/replace step and never saved `/root/results.pptx`
            | patch: recommend strengthening L2 “Confirm sandboxed artifact I/O…” to include explicit final deliverable existence assertion and PPTX embedded-object writeback checkpoint
  - iter_3 | diagnosis: same failure recurred; run ended without performing repack/save writeback, despite L2 rule “End-of-run deliverable gate”
            | patch: (none yet) — needs enforcement strengthening (e.g., mandatory pre-end checklist / explicit refusal to terminate until assert passes)
