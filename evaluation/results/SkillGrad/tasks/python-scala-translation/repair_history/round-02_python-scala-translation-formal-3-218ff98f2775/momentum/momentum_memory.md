### artifact-materialization-before-termination | workflow | ensure required output Scala files are created at specified paths before ending the turn
- anchor: (none yet)
- appeared_in: iter_0, iter_2
- description: The executor may complete a run without producing the deliverable at the mandated location, causing downstream compilation/testing to fail before semantic evaluation. This is not translation-quality but a workflow termination + artifact placement bug: either no output file is created (empty output inventory) or the code is written into a convenient project scaffold path while the required absolute path is missing (e.g., writing to `localtest/src/main/scala/.../Tokenizer.scala` but failing to create `/root/Tokenizer.scala`).
- latest_executor_action: Before ending the turn, enforce a hard “must materialize outputs” gate:
  1) identify the required output inventory from the task spec (exact paths + required top-level definitions);
  2) write the final Scala source to the exact required absolute path(s) (even if also maintaining a scaffold tree);
  3) re-open/read the written file(s) to confirm they exist, are non-empty, and contain the intended code;
  4) if a compiler is available, run `scalac` (Scala 2.13) against the required path(s) and iterate on errors; do not terminate while any required path is missing, empty, or fails compilation.
- remedy_log:
  - iter_0 | diagnosis: run ended with empty output inventory; required `/root/Tokenizer.scala` was never created/written
            | patch: (none yet) — to be added to L2 as a hard "must-write outputs" preflight + compile check before termination
  - iter_2 | diagnosis: executor wrote translation under a project subdirectory (`localtest/src/main/scala/tokenizer/Tokenizer.scala`) but did not save the required deliverable to `/root/Tokenizer.scala`
            | patch: (none yet) — still requires a path-compliance gate (write/copy to mandated absolute path) before termination
