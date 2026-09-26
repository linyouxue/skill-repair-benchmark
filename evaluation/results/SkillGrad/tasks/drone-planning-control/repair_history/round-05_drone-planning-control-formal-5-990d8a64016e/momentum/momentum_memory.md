### deliverables-loop-nonoptional | workflow | must run full per-command pipeline and write harness-facing results tree
- anchor: required-deliverables-loop-non-optional
- appeared_in: iter_5
- description: The harness grades based on an on-disk per-command results tree (typically `/root/results/<id>/...`). A run can be “execution_ok: true” while still failing because the agent never produced (or only partially produced) the required artifacts. The failure mode is ending the attempt without running the non-optional loop: enumerate all command IDs → for each: parse → plan → simulate → compute metrics → save `.npy`/`.json` → generate plots → then run an explicit completeness/readability check across all command IDs.

  This often co-occurs with prematurely switching into debugging mode (e.g., attempting to open verifier artifacts) before first generating the expected deliverables. It is distinct from controller-math correctness; even perfect gains will not pass if the tree is absent.
- latest_executor_action: Treat deliverables production as a first-class workflow invariant. At the start, enumerate the graded command inputs and create `<results_root>/<id>/` + `<results_root>/<id>/plots/` for each. For each command, run the full pipeline end-to-end and immediately serialize `planned_trajectory.npy`, `actual_trajectory.npy`, `metrics_3d.json`, `tuning_results.json`, and plot PNGs into `plots/`. Before exiting, run a completeness check that asserts every required file exists and can be loaded/parsed. If anything is missing/unreadable, fix and rerun the check; do not exit early.
- remedy_log:
  - iter_5 | diagnosis: evaluation failed due to missing `/root/results/<id>/...` artifacts; executor did not execute the “required deliverables loop” and ended the turn without writing harness-facing outputs
            | patch: (pending) strengthen L2 “Workflow: Required deliverables loop (non-optional)” to include a mandatory final on-disk completeness check and a hard stop-condition (“do not attempt verifier debugging until results tree exists”); consider elevating the runnable skeleton in references/deliverables_driver.md as the default execution plan

### evidence-access-enumerate-dont-guess | workflow | enumerate verifier/results dirs instead of hardcoding evidence filenames
- anchor: access-evidence-inside-the-sandbox
- appeared_in: iter_5
- description: When expected verifier/evidence files are missing, the executor may guess filenames/paths (e.g., `verifier/evidence.json`, `summary.json`) and proceed based on those assumptions. This blocks diagnosis and can lead to premature termination or wrong fixes. The correct mechanism is to list the available verifier/results directories and open what actually exists, using relative paths inside the sandbox root.
- latest_executor_action: If any referenced evidence file is missing/empty, immediately enumerate the relevant directories (verifier outputs, results root) to discover actual artifact names, then open/parse at least one non-empty verifier/trace artifact before making domain edits. If you cannot load any artifact, stop and fix artifact location/copying first.
- remedy_log:
  - iter_5 | diagnosis: executor guessed evidence filenames/paths instead of enumerating directories, preventing locating real verifier artifacts and contributing to early exit without deliverables
            | patch: (pending) no new rule needed (already present across skills); reinforce in overlays and consider adding an explicit “if you can’t find verifier artifacts, still proceed to produce required deliverables tree” note
