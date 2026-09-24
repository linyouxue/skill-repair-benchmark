### deliverable-commit-phase | workflow | always write required output artifact(s) and verify they exist before terminating
- anchor: (none yet)
- appeared_in: iter_0
- description: The executor sometimes completes (or partially completes) reasoning/compute steps but terminates without persisting the required deliverable file(s) to disk (e.g., missing `report.json`). This causes an immediate verifier failure regardless of internal correctness because the harness only grades on the presence and schema-validity of the artifact. The failure mode includes: producing no outputs at all; producing intermediate scratch outputs but not the final required file; or encountering an exception and exiting without writing a structured error report.
- latest_executor_action: Add a mandatory end-of-run “deliverable commit” phase: (1) identify required artifacts (here: `report.json`); (2) serialize the exact required JSON schema to disk; (3) immediately re-open/read the file (or list directory) to confirm it exists and is valid JSON; (4) if computation fails, still write `report.json` with explicit `error` fields and any partial results rather than exiting without an artifact.
- remedy_log:
  - iter_0 | diagnosis: run produced no deliverable artifact; `report.json` not created so verifier could not evaluate
            | patch: (none yet; bootstrap pattern record created from diagnosis)
