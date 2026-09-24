### [flink-query] Missing observable evidence access blocks diagnosis
- signal: failure
- pattern: evidence-access-blocked-by-sandbox
- anchor: (none)
- gap: The diagnoser’s first step—reading `trace.jsonl`—returns empty content, and attempts to read verifier evidence fail due to a sandbox path restriction (“escapes allowed project root”). With no trace content and no output inventory entries, there is no observable execution behavior to attribute to a code/skill mistake.
- proposed_change: Do not patch skill guidance. Fix harness/artifact collection so that (1) `iter_0/trace.jsonl` is non-empty and written under the allowed project root, and (2) verifier logs/artifacts are copied or symlinked into a sandbox-readable directory under the project root. After evidence is accessible, re-run diagnosis to identify the first concrete behavioral failure.

## WORKFLOW-THEMES

- (none this iteration)
