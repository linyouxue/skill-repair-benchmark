### [syzkaller-ppdev-syzlang] missing required deliverables (no output artifacts created)
- signal: failure
- pattern: deliverables-presence-check
- anchor: (none)
- gap: The trajectory reached finalization without writing the two required syzlang description files to the exact requested output paths; the output inventory is empty. Existing guidance covers compiling with `make descriptions` and fixing errors, but does not impose a workflow gate: “create deliverables at specified absolute paths and verify they persist” before ending.
- proposed_change: Add a cross-skill L2 workflow rule (new H2, e.g., `## Deliverables gate: write + verify required output files`) that triggers whenever the user specifies output file paths. The rule should require: enumerate deliverables early; write files explicitly (not just edit in-editor buffers); before finalizing run `ls -l` + `sed -n 1,40p` on each required path; then run `make descriptions` (if applicable) and re-check files still exist after build/cleanup.

## WORKFLOW-THEMES
- (none this iteration)
