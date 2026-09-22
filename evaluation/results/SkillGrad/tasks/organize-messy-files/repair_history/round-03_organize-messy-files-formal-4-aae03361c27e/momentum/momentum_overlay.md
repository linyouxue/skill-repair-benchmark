### [organize-messy-files] Agent ended without performing required sorting workflow
- signal: failure
- pattern: workflow-must-complete-fixed-taxonomy-loop
- anchor: post-write-verification
- gap: The run terminates with "end_turn" and <n_skill_invocations> = 0; no evidence of entering the file-organizer workflow at all. Specifically, the workspace was not reorganized into the required five subject folders and there were no folder creations or file moves, violating “After organizing them, you will have 5 folders… No other files left out.” This indicates a missing/unenforced completion gate that prevents stopping before the create→classify→move→verify loop is executed and the end-state is asserted.
- proposed_change: Strengthen L2 file-organizer at the post-write-verification anchor to include an explicit pre-termination checklist and hard stop condition: do not call end_turn unless (1) the five required folders exist, (2) an inventory over the stable scope root has been performed, (3) every file has been assigned and moved into exactly one of the five folders, and (4) a final re-inventory confirms zero files remain outside those folders. Consider adding a short “Before end_turn, run: find <root> -maxdepth 1 -type f (should be empty)” example to make the end-state test operational.

## WORKFLOW-THEMES

- (none this iteration)
