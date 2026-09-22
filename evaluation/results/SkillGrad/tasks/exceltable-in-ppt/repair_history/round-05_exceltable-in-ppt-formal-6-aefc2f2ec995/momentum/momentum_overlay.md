### [exceltable-in-ppt] Ended the run without writing the required output PPTX
- signal: failure
- pattern: deliverable-writeback-and-final-existence-check
- anchor: confirm-sandboxed-artifact-i-o-before-operating
- gap: The run ended with `end_turn` without any extract/edit/repack/save actions ("no skill invocations and no substantive tool-driven edits") and without producing the required deliverable at `/root/results.pptx`. This is a stronger form of the recurring pattern: not only was writeback skipped, but the executor also bypassed the L2 **“End-of-run deliverable gate (MANDATORY)”** and did not run an existence+non-empty assertion on the required output path before terminating.
- proposed_change: Strengthen the L2 gate at `confirm-sandboxed-artifact-i-o-before-operating` from advisory to an explicit stop-condition checklist: before `end_turn`, the executor must (1) name the exact expected deliverable path, (2) show the command/snippet used to assert existence+size>0, and (3) if the check cannot be executed, explicitly refuse to terminate and instead report being blocked. Additionally add a mid-work “no-op guard”: if no file-modifying operation has been performed yet, do not allow `end_turn`—restart by unpacking the PPTX and locating the embedded OLE workbook.

## WORKFLOW-THEMES

- (none this iteration)
