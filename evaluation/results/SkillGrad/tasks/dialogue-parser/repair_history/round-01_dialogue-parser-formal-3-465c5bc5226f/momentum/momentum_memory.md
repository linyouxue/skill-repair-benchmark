# Pattern record (updated)

### always-write-required-artifacts | workflow | ensure required deliverables are written to disk at specified paths before ending run
- anchor: (none yet)
- appeared_in: iter_0
- description: The executor completes some portion of the reasoning/implementation but fails the task by not materializing required output files. In this iteration, neither `/app/dialogue.json` nor `/app/dialogue.dot` was created; the run ended without emitting artifacts. This is a pipeline-completion failure independent of parsing correctness: even partial/approximate outputs are required for grading.
- latest_executor_action: Identify required deliverables and their exact paths early. Before finalizing, unconditionally write all required artifacts to disk (even if parsing is incomplete, emit best-effort valid structures), then perform an explicit post-write artifact check: verify each required file exists, is non-empty, and (when applicable) parses/loads successfully.
- remedy_log:
  - iter_0 | diagnosis: run produced no required outputs (`/app/dialogue.json` and `/app/dialogue.dot` missing)
            | patch: (none yet; initial pattern capture)
