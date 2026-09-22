### [organize-messy-files] Missing evidence due to path access
- signal: failure
- pattern: harness-artifacts-inaccessible
- anchor: (none)
- gap: Pre-analysis evidence loading could not access trace/verifier/skills artifacts; reads returned empty content or “file not found / escapes allowed project root”, so no agent trajectory step or grader finding is observable.
- proposed_change: Not a skill-level patch. Fix harness/artifact placement: ensure `trace.jsonl`, `assessment.json`/verifier summaries, and evolved skill files are copied/symlinked into the sandbox-allowed project root for this run directory (or update the sandbox allowlist/root). Then rerun and re-diagnose using the first actual agent failure.

## WORKFLOW-THEMES

- (none this iteration)
