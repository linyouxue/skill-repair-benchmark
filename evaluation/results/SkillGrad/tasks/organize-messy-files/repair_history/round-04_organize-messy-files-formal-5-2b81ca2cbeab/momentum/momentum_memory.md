# Pattern record (updated)

### workflow-must-complete-fixed-taxonomy-loop | workflow | executor prematurely terminates without performing required create→classify→move→verify loop for fixed-taxonomy organization tasks
- anchor: post-write-verification
- appeared_in: iter_3, iter_4
- description: For “organize everything into N specific folders; no other files left out” tasks, the executor may stop (end_turn) before executing any organizing actions at all, or after a partial pass, leaving files outside the required target folders. Mechanism: absence (or non-salience) of an explicit completion gate causes the executor to treat planning/acknowledging as sufficient and to terminate without confirming the required end-state on disk. In iter_4, this manifested as producing virtually no reorganization: the required subject folders were not created/populated and most files stayed outside the target taxonomy.
- latest_executor_action: Treat fixed-taxonomy organization tasks as requiring a mandatory completion checklist before termination: (1) create the exact required destination folders, (2) inventory all candidate files under the scope root, (3) classify each file using lightweight inspection appropriate to format, (4) move every file exactly once into exactly one destination folder (log moves if many), and (5) re-inventory to assert end-state: within the scope root, no files remain outside the target folders and the required folders exist with non-zero contents as expected. If the end-state assertion fails, do not end the turn; continue organizing or undo/repair using the move log.
- remedy_log:
  - iter_3 | diagnosis: agent performed zero sorting actions and ended immediately; no folder creation/moves; violated “After organizing them, you will have 5 folders… No other files left out.”
            | patch: add an explicit “must complete fixed-taxonomy loop + end-state assertion before end_turn” rule, anchored at L2 file-organizer Post-write verification.
  - iter_4 | diagnosis: agent again failed to execute core organizing actions; required 5 folders not created/populated; run ended after tool calls with no classify→move loop and no end-state verification.
            | patch: (proposed) strengthen L2 Post-write verification with a hard “no-op guard”: if file count outside target folders is unchanged (or >0) after execution, treat as incomplete and continue; add an explicit requirement to create the exact folder names before any classification.

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
