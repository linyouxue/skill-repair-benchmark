### [organize-messy-files] Skipped core organizing requirement by operating on a tiny downloaded set instead of inventorying and organizing the provided dataset
- signal: failure
- pattern: inspect-scope-before-acting
- anchor: inspect-first-inventory
- gap: The executor never performed the file-organizer "Inspect first (inventory)" step on the real dataset directory containing the >100 files. Instead, the earliest execution phase was dominated by downloading/creating a small number of files and then stopping, never reaching the required sequence: "create 5 subject folders → classify existing files → move every file into exactly one folder → verify no leftovers".
- proposed_change: In file-organizer L2, strengthen/clarify the inventory guardrail to be a hard precondition: (1) locate dataset root and record it as the stable scope, (2) run inventory commands and report counts/types, (3) if the task is fixed-taxonomy classification, immediately create the required target folders and enter an iterative classify+move loop over *all* files under scope (with move log), (4) finish with a re-inventory assertion that zero files remain outside the targets and counts match.

## WORKFLOW-THEMES

- (none this iteration)
