### [software-dependency-audit] missing required CSV deliverable at `/root/security_audit.csv`
- signal: failure
- pattern: write-and-verify-required-deliverable
- anchor: (none)
- gap: The run ended without writing the required output artifact; grader saw `Output inventory: []` and `/root/security_audit.csv` was missing/empty. The current guidance focuses on scanning/parsing/report generation but does not enforce an explicit “write the CSV to the exact required path, then verify it exists + has correct header” termination gate.
- proposed_change: Add an L2 workflow rule (new anchor) in the reporting skill to enforce a completion checklist: always write `/root/security_audit.csv` with the exact schema, then run a verification step (`ls -l /root/security_audit.csv`, `head -n 2`, row count) before terminating. If no HIGH/CRITICAL findings, still write a header-only CSV (or explicit empty report per task spec) and verify.

## WORKFLOW-THEMES

- (none this iteration)
