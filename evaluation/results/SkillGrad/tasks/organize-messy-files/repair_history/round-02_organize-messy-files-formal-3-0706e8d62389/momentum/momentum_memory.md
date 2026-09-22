# Pattern record (updated)

### inspect-scope-before-acting | workflow | executor acts on assumed/irrelevant file set instead of inventorying the actual dataset and freezing scope
- anchor: inspect-first-inventory
- appeared_in: iter_2
- description: The executor begins execution (downloads, generates, or operates on a tiny or wrong directory) without first locating and inventorying the real on-disk dataset that must be organized. This typically shows up as performing unrelated file creation/fetching and never reaching the required "create target taxonomy → classify → move all existing files" loop. Mechanism: the executor trusts prompt phrasing or its own plan over filesystem evidence and fails to record and keep a stable scope root.
- latest_executor_action: Before any mutations or external fetching, locate the actual dataset root directory, then run an inventory (top-level listing, file counts, type sampling). Explicitly record "scope root" and keep it stable. If the objective is organizing into a fixed taxonomy, create the target folders immediately and iteratively classify+move every file under the scope until none remain outside targets; then re-inventory to verify zero leftovers.
- remedy_log:
  - iter_2 | diagnosis: agent skipped inventory and never operated on the provided >100-file dataset; instead ran download/creation steps and ended with only a few files in one location.
            | patch: add/strengthen L2 file-organizer "Inspect first (inventory)" decision rule with explicit guardrail: prohibit downloading/creating substitute data before inventorying dataset; add explicit fixed-taxonomy execution loop + end-state verification.

### harness-artifacts-inaccessible | workflow | missing trace/verifier/skill artifacts prevents diagnosis and is not skill-controllable
- anchor: (none yet)
- appeared_in: iter_0
- description: The executor (and diagnosis pipeline) cannot access required run artifacts (trace.jsonl, assessment/verifier outputs, or skill files) due to filesystem allowlist/project-root restrictions, missing files, or empty reads. With no observable agent actions or grader findings, there is no basis to map failures to a correctable skill rule.
- latest_executor_action: When evidence files are empty or blocked, stop skill-level diagnosis and treat as harness failure: ensure trace/verifier outputs and evolved_skills are present within the allowed project root (copy/symlink, fix paths/allowlist), then rerun to obtain an actionable first observable agent error.
- remedy_log:
  - iter_0 | diagnosis: Unable to retrieve any execution trace/verifier evidence or skill rules; tool reads return empty or “file not found / escapes allowed project root”.
            | patch: No skill patch; recommend harness fix (copy/symlink artifacts into allowed root or update sandbox allowlist) and rerun diagnosis.
