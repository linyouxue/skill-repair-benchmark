### output-finalization-write-required-artifact | workflow | executor computes result but fails to write the required output file/format
- anchor: (none yet)
- appeared_in: iter_0
- description: The executor can complete analysis successfully (execution_ok: true) but still fail the task by not persisting the final scalar answer to the grader-required artifact path. Mechanism: termination occurs with no output inventory, so the verifier cannot read the result (e.g., missing `/root/period.txt`). This is a workflow finalization lapse rather than an algorithmic error.
- latest_executor_action: Before ending any run, execute a hard “finalization checklist”: (1) identify the required output artifact path(s) and exact formatting constraints, (2) write the final value(s) to the exact path(s) with no extra text (e.g., single float rounded to 5 decimals), and (3) re-open/read back the file(s) to confirm existence and parseability. Do not terminate until this passes.
- remedy_log:
  - iter_0 | diagnosis: run terminated with empty Output inventory; required `/root/period.txt` absent, so period could not be graded
            | patch: propose adding an explicit finalization rule/checklist to workflow guidance (L2) used by all period-finding tasks
