### [python-scala-translation] missing required Scala artifact `/root/Tokenizer.scala`
- signal: failure
- pattern: artifact-materialization-before-termination
- anchor: (none)
- gap: The run terminated without executing any file creation/write step for the required deliverable. The diagnosis notes: "No deliverable was produced" and the output inventory is empty, so the verifier could not compile/test anything.
- proposed_change: Add an L2 workflow rule (new section) that blocks termination until (1) `/root/Tokenizer.scala` is written, (2) the file is re-read to confirm contents, and (3) a `scalac` compile check (Scala 2.13) is attempted when available; on failure, continue iterating rather than ending.

## WORKFLOW-THEMES

- (none this iteration)
