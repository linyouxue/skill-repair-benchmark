### [exceltable-in-ppt] terminated without producing `/root/results.pptx` (missing repack/save writeback)
- signal: failure
- pattern: deliverable-writeback-and-final-existence-check
- anchor: confirm-sandboxed-artifact-i-o-before-operating
- gap: The guidance already contains an explicit “End-of-run deliverable gate” (assert required deliverable path exists and is non-empty; if not, do not end the turn). The run nevertheless executed `end_turn` while no deliverable existed, meaning the executor failed to execute (or to treat as blocking) the pack/save writeback + existence assertion step.
- proposed_change: Strengthen the L2 deliverable gate from advisory to mandatory by adding a pre-termination checklist that must be executed immediately before `end_turn` (e.g., “last action before end_turn must be a filesystem assertion + directory listing for the deliverable path”). If this continues to recur, fan-out into an L3 runnable “PPTX embedded workbook writeback algorithm” with explicit steps: locate embedded OLE part → replace updated xlsx payload → repack pptx → verify output at required path.

## WORKFLOW-THEMES

- (none this iteration)
