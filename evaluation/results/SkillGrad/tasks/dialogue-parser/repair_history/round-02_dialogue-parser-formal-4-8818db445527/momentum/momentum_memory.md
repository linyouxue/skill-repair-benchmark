# Pattern record (updated)

### always-write-required-artifacts | workflow | ensure required deliverables are written to disk at specified paths before ending run
- anchor: plan-the-run-minimal
- appeared_in: iter_0, iter_3
- description: The executor completes some portion of the reasoning/implementation but fails the task by not materializing required output files. This is a pipeline-completion failure independent of parsing correctness: even partial/approximate outputs are required for grading. In iter_3, the output inventory contained only the input `script.txt`; neither `/app/dialogue.json` nor `/app/dialogue.dot` was created, implying the run ended without performing the “write outputs + artifact check” phase.
- latest_executor_action: At start, list required deliverables with exact absolute paths. Before finalizing, unconditionally write all required artifacts to disk (best-effort valid structures; if export fails, write safe placeholders), then perform the explicit post-write artifact check: verify each required file exists, is non-empty, and (when applicable) parses/loads successfully (e.g., `json.load` for `/app/dialogue.json`). Do not end the run until the inventory passes.
- remedy_log:
  - iter_0 | diagnosis: run produced no required outputs (`/app/dialogue.json` and `/app/dialogue.dot` missing)
            | patch: (none yet; initial pattern capture)
  - iter_3 | diagnosis: output inventory contained only `script.txt`; final export + artifact-check step was omitted, so `/app/dialogue.json` and `/app/dialogue.dot` were never written
            | patch: re-anchor pattern to existing L2 rule ("Plan the run (minimal)" + mandatory artifact check) and rely on L3 procedure `references/export-and-artifact-check.md` for branched best-effort export + verification
