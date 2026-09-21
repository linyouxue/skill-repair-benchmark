### required-artifact-answers-json | workflow | ensure mandatory /root/answers.json is written and validated before termination
- anchor: (none yet)
- appeared_in: iter_0
- description: The executor can complete all reasoning but still fail the task by ending the run without producing the required output artifact. In this batch, the output inventory was empty: no /root/answers.json existed at end_turn, so the verifier could not find the mandated file. This is a workflow/packaging failure independent of SEC/13F domain logic.
- latest_executor_action: Before ending the run, always (1) create /root/answers.json, (2) ensure it is valid JSON, (3) ensure it matches the exact required schema/keys (e.g., q1_answer..q4_answer as specified by the task), and (4) re-open/read back the file to confirm it exists at the correct path and parses successfully. Only then terminate.
- remedy_log:
  - iter_0 | diagnosis: agent terminated without writing required /root/answers.json; output inventory empty
            | patch: (pending) add a pre-exit required-artifact checklist rule and an explicit “write + read-back verify” step
