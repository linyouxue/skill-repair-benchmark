### artifact-materialization-before-termination | workflow | ensure required output Scala files are created at specified paths before ending the turn
- anchor: (none yet)
- appeared_in: iter_0
- description: The executor may complete a run without producing any deliverable files, causing downstream compilation/testing to fail immediately (empty output inventory). This is not a translation-quality issue but a workflow termination bug: the agent reaches an end-of-turn completion without ever writing the required artifact (e.g., `/root/Tokenizer.scala`).
- latest_executor_action: Before ending the turn, confirm the required output inventory exists: write the translated Scala source to the exact required path(s), then re-open/read those files to confirm they were created and contain the intended code. If a compile step is available, run it (e.g., `scalac` for Scala 2.13) and iterate on errors instead of terminating.
- remedy_log:
  - iter_0 | diagnosis: run ended with empty output inventory; required `/root/Tokenizer.scala` was never created/written
            | patch: (none yet) — to be added to L2 as a hard "must-write outputs" preflight + compile check before termination
