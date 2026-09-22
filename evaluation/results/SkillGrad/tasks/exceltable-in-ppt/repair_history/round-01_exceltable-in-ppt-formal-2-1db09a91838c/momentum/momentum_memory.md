# Pattern record (iteration 0)

### harness-artifact-availability | workflow | missing/empty trace and inaccessible artifacts prevents skill-level diagnosis
- anchor: (none yet)
- appeared_in: iter_0
- description: The diagnoser cannot observe the agent’s trajectory or outputs because the trace file is empty and/or required artifacts (e.g., result.json, verifier evidence, skill registry/files) are missing or outside the permitted sandbox root. With no recorded actions, the earliest observable “failure” is artifact absence rather than an agent decision. This is not skill-controllable: no rule inside pptx/xlsx guidance can repair missing logs after the run.
- latest_executor_action: When execution evidence is missing, halt skill-level diagnosis and escalate as a harness/environment issue. Ensure runs export trace and outputs into the permitted project root and that all referenced evidence paths are accessible to postmortem tooling.
- remedy_log:
  - iter_0 | diagnosis: empty trace.jsonl and missing/inaccessible evaluation artifacts; cannot attribute failure to an agent step
            | patch: record as harness-level failure; no skill-file change recommended
