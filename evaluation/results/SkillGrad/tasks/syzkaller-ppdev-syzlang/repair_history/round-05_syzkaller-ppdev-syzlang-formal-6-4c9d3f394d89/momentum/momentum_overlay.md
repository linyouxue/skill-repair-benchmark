### [syzkaller-ppdev-syzlang] run ended with empty output inventory; required deliverables were never created
- signal: failure
- pattern: deliverables-presence-check
- anchor: deliverables-gate-write-verify-required-output-files
- gap: executor ended (“end_turn”) without executing the mandatory deliverables gate actions: "Within the first 1–2 tool calls, create … minimal non-empty stubs" and the blocking checkpoint ("verify … using ls … and preview … with sed"). Diagnosis notes there were no tool calls / trace is empty, so nothing was ever persisted to `/opt/syzkaller/sys/linux/dev_ppdev.txt` or `dev_ppdev.txt.const`.
- proposed_change: strengthen the L2 deliverables gate to include a hard guardrail for “zero tool calls so far”: the next action must be `mkdir -p` + write both stubs + `ls -l`/`sed -n` checkpoint before any analysis. If this is already first, consider duplicating a minimal 2-line “deliverables-first” banner at the very top of each SKILL.md so it is harder to skip.

## WORKFLOW-THEMES

- (none this iteration)
