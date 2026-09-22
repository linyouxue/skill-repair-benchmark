# Pattern record (initial)

### harness-artifacts-inaccessible | workflow | missing trace/verifier/skill artifacts prevents diagnosis and is not skill-controllable
- anchor: (none yet)
- appeared_in: iter_0
- description: The executor (and diagnosis pipeline) cannot access required run artifacts (trace.jsonl, assessment/verifier outputs, or skill files) due to filesystem allowlist/project-root restrictions, missing files, or empty reads. With no observable agent actions or grader findings, there is no basis to map failures to a correctable skill rule.
- latest_executor_action: When evidence files are empty or blocked, stop skill-level diagnosis and treat as harness failure: ensure trace/verifier outputs and evolved_skills are present within the allowed project root (copy/symlink, fix paths/allowlist), then rerun to obtain an actionable first observable agent error.
- remedy_log:
  - iter_0 | diagnosis: Unable to retrieve any execution trace/verifier evidence or skill rules; tool reads return empty or “file not found / escapes allowed project root”.
            | patch: No skill patch; recommend harness fix (copy/symlink artifacts into allowed root or update sandbox allowlist) and rerun diagnosis.
