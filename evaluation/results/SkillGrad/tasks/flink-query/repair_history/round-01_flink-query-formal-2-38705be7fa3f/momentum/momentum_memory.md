### evidence-access-blocked-by-sandbox | workflow | diagnoser cannot attribute failure because trace/verifier artifacts are inaccessible or empty
- anchor: (none yet)
- appeared_in: iter_0
- description: When the executor/diagnoser attempts to inspect run evidence (e.g., `trace.jsonl`, verifier logs), the artifacts may be unreadable, empty, or located outside the sandbox-allowed project root. In this condition, no concrete behavioral failure can be localized to a skill mistake because there is no observable execution trace or output inventory. This is an environment/harness issue rather than a guidance or reasoning failure.
- latest_executor_action: Before proposing any skill edits or attributing failure to planning/execution, verify that (a) the harness exported a non-empty trace into the allowed project root, and (b) verifier evidence paths are accessible within sandbox constraints. If evidence is missing/inaccessible, stop diagnosis at “insufficient evidence,” and request/perform artifact relocation (copy/symlink into allowed root) or harness configuration fixes to emit logs where they can be read.
- remedy_log:
  - iter_0 | diagnosis: trace file empty and verifier evidence path escaped allowed project root, preventing localization of any earlier behavioral failure
            | patch: none (requires harness/artifact export fix, not skill text)
