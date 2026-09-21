### [dialogue-parser] Missing required output artifacts (/app/dialogue.json, /app/dialogue.dot)
- signal: failure
- pattern: always-write-required-artifacts
- anchor: plan-the-run-minimal
- gap: Despite L2 instructions to (a) identify deliverables up front and (b) end with an explicit artifact check, the run ended with only the input `script.txt` present. The executor appears to have skipped the entire “write outputs + artifact check” phase: no serialization to `/app/dialogue.json` and no DOT source written to `/app/dialogue.dot`.
- proposed_change: Strengthen the L2 “Plan the run (minimal)” section to mandate an explicit end-of-run export routine (“write both files, then verify existence/non-empty and JSON loads”), and add an L2 pointer that this step must follow the runnable algorithm in `references/export-and-artifact-check.md` (including its Branch B fallback placeholders) whenever filesystem deliverables are required.

## WORKFLOW-THEMES

- (none this iteration)
