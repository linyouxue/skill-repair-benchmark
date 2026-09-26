### [drone-planning-control] Sandbox path access violation blocks reading trace/verifier artifacts
- signal: failure
- pattern: sandbox-path-access
- anchor: (none)
- gap: Evidence-gathering attempted with absolute host paths (e.g. `/home/.../trace.jsonl`) that violate sandbox constraints (“path escapes the allowed project root”), then tried `trace.jsonl` relative to CWD which did not exist. This prevented inspection of the execution trace, verifier evidence, and skill rules, so no grounded diagnosis or edits could occur.
- proposed_change: Add an L2 workflow rule (new anchor, e.g. `sandbox-evidence-access`) to always (1) discover/confirm the sandbox root via directory listing, (2) use only harness-provided relative paths under the allowed root for `read_file`, and (3) if artifacts are outside the allowed root, copy them into the workspace/results directory before reading. Also add a stop-condition: if evidence cannot be accessed, do not proceed to domain fixes.

## WORKFLOW-THEMES

- (none this iteration)
