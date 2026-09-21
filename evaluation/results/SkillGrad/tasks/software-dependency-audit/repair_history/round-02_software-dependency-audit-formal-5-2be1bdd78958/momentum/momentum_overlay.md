### [software-dependency-audit] Missing required output artifact `/root/security_audit.csv`
- signal: failure
- pattern: write-and-verify-required-deliverable
- anchor: complete-the-deliverable-workflow
- gap: The run terminated without writing the required CSV deliverable at the exact path `/root/security_audit.csv`. This skips the vulnerability-csv-reporting skill’s “Complete-the-deliverable workflow” steps: “Always write the CSV …” and “After writing, run a hard verification gate: file exists at the exact path, header matches …”. The failure is specifically end-of-run without an artifact gate.
- proposed_change: Strengthen/activate the completion gate by making it a last mandatory step before termination: explicitly re-check the required output path from the prompt/spec, write the CSV (header-only if no findings) to `/root/security_audit.csv`, then verify (a) file exists at that exact path, (b) header equals expected schema, and (c) row count matches expectations. Consider promoting this as an unconditional end-of-run checklist item for all file-deliverable tasks.

## WORKFLOW-THEMES

- (none this iteration)
