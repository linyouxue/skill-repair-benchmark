### [dialogue-parser] Missing required artifact outputs (/app/dialogue.json, /app/dialogue.dot)
- signal: failure
- pattern: always-write-required-artifacts
- anchor: plan-the-run-minimal
- gap: The run ended (`end_turn`) without executing the mandatory export → artifact check routine: no JSON or DOT file was written, and no existence/non-empty / `json.load` verification was performed. This repeats the known failure mode where the executor completes some reasoning but omits the filesystem deliverables pipeline entirely.
- proposed_change: Strengthen the L2 "Plan the run (minimal)" section with an explicit end-of-run guardrail: before `end_turn`, execute the L3 procedure `references/export-and-artifact-check.md` and confirm the required paths (e.g., `/app/dialogue.json`, `/app/dialogue.dot`) exist and are non-empty; if not, block termination and run Branch B placeholders immediately, then re-verify.

## WORKFLOW-THEMES

- (none this iteration)
