### produce-required-deliverables-and-verify | workflow | ensure required output artifacts are written and verified before finishing
- anchor: (none yet)
- appeared_in: iter_0
- description: The executor ends the run without writing any of the required deliverables (e.g., `compressed_video.mp4` and `compression_report.json`). This is a workflow-level omission: regardless of how detection/processing proceeds internally, the workflow must always materialize the requested artifacts and confirm they exist and are readable (JSON parse) before `end_turn`. This pattern often presents as an empty output inventory `[]` at assessment time.
- latest_executor_action: Treat deliverables as mandatory. Before ending the turn: (1) create/write every required output file at the specified paths; (2) if a deliverable depends on intermediate results, generate minimal viable intermediates to unblock output; (3) run an existence + non-empty check on each output; (4) parse/validate JSON outputs against the expected schema keys; (5) if any step fails, do not end—surface a clear error and attempt the simplest fallback that still produces valid artifacts.
- remedy_log:
  - iter_0 | diagnosis: output inventory was empty; required files `compressed_video.mp4` and `compression_report.json` were missing
            | patch: (proposed) add an explicit end-of-task "materialize deliverables + verify" checkpoint to the video-silence-remover workflow skill; ensure report/video generation steps are mandatory, not optional
