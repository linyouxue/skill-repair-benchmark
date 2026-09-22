### [exceltable-in-ppt] skipped required PPTX writeback; no `/root/results.pptx` produced
- signal: failure
- pattern: deliverable-writeback-and-final-existence-check
- anchor: confirm-sandboxed-artifact-i-o-before-operating
- gap: The run terminated without persisting the edited embedded workbook back into the PPTX and without saving a new presentation to the required output path. The PPTX/XLSX skills mention verifying output existence, but the task-specific “extract → edit → re-embed/replace OLE part → save results.pptx” checkpoint chain was not executed, so the verifier only found the original `input.pptx`.
- proposed_change: In both `pptx/SKILL.md` and `xlsx/SKILL.md` under **Workflow: Confirm sandboxed artifact I/O before operating**, add an explicit *end-of-run deliverable gate*: “Before finishing, assert the required deliverable path exists and is non-empty; if not, do not terminate.” Also add a PPTX-specific sub-bullet for embedded Excel/OLE edits: “After modifying an embedded workbook, you must write it back into the embedded part and repack/save the PPTX to the harness-required output filename (e.g., `/root/results.pptx`), not just edit extracted files.”

## WORKFLOW-THEMES

- (none this iteration)
