### deliverable-enforcement-and-output-verification | workflow | ensure required output artifacts are created at specified paths before ending
- anchor: (none yet)
- appeared_in: iter_0
- description: The executor can complete a run without producing any deliverables, even when the task success condition is entirely defined by the presence of files at required paths (e.g., `/root/redacted/paper{1-3}.pdf`). This failure mode typically shows up as an empty output inventory and a normal termination, indicating that the executor did not (a) create the output directory, (b) run the core transformation producing outputs, and/or (c) verify that outputs exist and are valid (non-empty, openable PDFs).
- latest_executor_action: Treat required deliverable paths as hard acceptance criteria. Before ending: create required directories; generate every required output file at the exact path; then verify existence (`ls -l`), openability (e.g., `pypdf`/`fitz` open), and basic sanity (non-zero bytes, expected page count). If any required artifact is missing or invalid, do not end—retry with an alternate toolchain/method until all artifacts pass checks.
- remedy_log:
  - iter_0 | diagnosis: run terminated with no outputs at `/root/redacted/paper{1-3}.pdf` (output inventory empty)
            | patch: (none yet; to be added to skill guidance)
