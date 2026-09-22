### [dialogue-parser] missing required output artifacts (/app/dialogue.json, /app/dialogue.dot)
- signal: failure
- pattern: always-write-required-artifacts
- anchor: plan-the-run-minimal
- gap: The run terminated at `end_turn` without performing the mandated end-of-run guardrail: no explicit export step, no writes to the required absolute paths, and no post-write artifact verification. The filesystem output inventory confirms only `script.txt` exists, so the executor either skipped or forgot the “export → artifact check” routine despite it being explicitly stated in `SKILL.md`.
- proposed_change: Strengthen the L2 “End-of-run guardrail” instruction under `## Plan the run (minimal)` to require an explicit, checkable completion ritual: (1) list the required paths verbatim, (2) show or call the exact export routine (pointer to `references/export-and-artifact-check.md`), and (3) state the verification results (existence + non-empty + JSON loads) immediately before `end_turn`. If this still recurs, add a harder stop condition like “Do not call end_turn until you have re-opened /app/dialogue.json and successfully json.load’d it.”

## WORKFLOW-THEMES

- (none this iteration)
