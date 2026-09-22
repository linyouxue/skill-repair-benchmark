### [python-scala-translation] required Scala file not written to mandated path (/root/Tokenizer.scala)
- signal: failure
- pattern: artifact-materialization-before-termination
- anchor: (none)
- gap: Executor produced a Scala translation file, but placed it in a scaffold project path (`localtest/src/main/scala/tokenizer/Tokenizer.scala`) while the required deliverable path `/root/Tokenizer.scala` was missing. This indicates the workflow lacks a hard output-inventory/path compliance check before termination (it may “finish” after writing *some* Scala file, without validating the *mandated* path).
- proposed_change: Add an L2 workflow gate (or reuse/relocate the existing "Materialize required artifacts before ending" content) that explicitly: (1) parses required absolute output paths from the prompt, (2) writes the final code to those exact paths as the last step (copy from scaffold tree if needed), (3) re-reads the file(s) to confirm existence + non-empty, and (4) optionally compiles. Ensure the rule mentions that writing into `src/main/scala/...` is insufficient unless the spec allows it.

## WORKFLOW-THEMES

- (none this iteration)
