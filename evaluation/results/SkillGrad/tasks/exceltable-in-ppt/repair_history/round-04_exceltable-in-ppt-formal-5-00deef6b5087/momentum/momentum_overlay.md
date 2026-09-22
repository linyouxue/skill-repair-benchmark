### [exceltable-in-ppt] terminated without writing the required updated PPTX deliverable
- signal: failure
- pattern: deliverable-writeback-and-final-existence-check
- anchor: confirm-sandboxed-artifact-i-o-before-operating
- gap: The run ended in `end_turn` without performing the mandated end-of-run deliverable gate. Concretely, no repack/save step produced `/root/results.pptx` (or an in-sandbox equivalent), and there was no immediate pre-termination existence+non-empty assertion; the output inventory contained only the original `input.pptx`.
- proposed_change: Strengthen the L2 section **“Workflow: Confirm sandboxed artifact I/O before operating”** into an explicit pre-`end_turn` checklist with a hard stop: add a final bullet that says (verbatim, or close) “If you are about to `end_turn`, you MUST first run `assert out_path.exists() and out_path.stat().st_size > 0`; if you cannot run it (no code execution), then do not `end_turn`—instead state that you are blocked from verifying the deliverable.” Also add a PPTX-specific sub-check: “After editing embedded XLSX/OLE parts, re-embed + pack the PPTX, then run the assertion.”

## WORKFLOW-THEMES

- (none this iteration)
