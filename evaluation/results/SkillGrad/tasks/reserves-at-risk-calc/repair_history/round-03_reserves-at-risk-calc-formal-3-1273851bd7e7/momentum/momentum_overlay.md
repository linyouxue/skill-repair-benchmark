### [reserves-at-risk-calc] Missing verifier evidence access
- signal: failure
- pattern: verifier-evidence-path-allowlist | new
- anchor: (none)
- gap: Diagnoser tried to read a specific verifier evidence path (`/.../verifier/evidence.json`) that was not present, then attempted to list/read a verifier directory outside the sandbox allowlist (“escapes the allowed project root”). This prevents establishing what spreadsheet output was wrong, so any spreadsheet-skill patch would be unfounded.
- proposed_change: Add a diagnoser-side workflow rule for evidence discovery constrained to the allowed project root: if `verifier/evidence.json` is missing, enumerate and try in-root alternatives (e.g., `verifier/*.json`, `verifier/results.json`, `verifier/report.txt`, plus `assessment.json`/trace). If none accessible, label as harness/evidence-collection issue and stop.

## WORKFLOW-THEMES

- (none this iteration)
