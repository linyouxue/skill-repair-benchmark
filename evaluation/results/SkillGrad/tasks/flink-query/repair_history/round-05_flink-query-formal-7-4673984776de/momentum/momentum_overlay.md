### [flink-query] evidence inaccessible due to sandbox path violations during initial file reads
- signal: failure
- pattern: verify-in-root-evidence-paths
- anchor: verify-evidence-is-accessible-before-diagnosing-or-proposing-changes
- gap: the executor attempted to collect diagnostic evidence by reading absolute paths outside the sandbox-allowed project root (e.g., `/app/workspace/...` and verifier artifact locations), causing “file not found” / “escapes allowed project root” errors and preventing inspection of stdout/stderr/output files or workspace sources.
- proposed_change: strengthen L2 Workflow 0 (“Verify Evidence Is Accessible…”) to include an explicit step: *when a referenced path is absolute/out-of-root, map it to the exported in-root workspace/artifacts directory* (e.g., under `.../batch/flink-query/workspace` and `.../iter_6/`). Add a concrete instruction to stop retrying blocked paths and instead search/derive the corresponding in-root filenames before proceeding with code-level diagnosis.

## WORKFLOW-THEMES

- (none this iteration)
