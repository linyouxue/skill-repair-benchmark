### [paper-anonymizer] missing required redacted PDF outputs at the specified destination paths
- signal: failure
- pattern: deliverable-enforcement-and-output-verification
- anchor: (none)
- gap: The trajectory ended without performing the essential file-producing steps: creating `/root/redacted/`, processing `/root/paper{1-3}.pdf`, and writing outputs to `/root/redacted/paper{1-3}.pdf`. There was no end-of-run gate that checked `Output inventory`/filesystem for required artifacts before `end_turn`.
- proposed_change: Add an L2 "deliverable enforcement" rule to the redaction workflow: (1) create output directory, (2) write outputs to exact required paths, (3) verify outputs exist and are valid PDFs (non-empty bytes + open with `fitz`/`pypdf` + basic text-retention check), and (4) block termination until all required artifacts pass.

## WORKFLOW-THEMES

- (none this iteration)
