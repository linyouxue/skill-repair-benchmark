# Pattern record (initial)

### persist-required-deliverables | workflow | ensure required output artifact is written to the specified path and verified before termination
- anchor: (none yet)
- appeared_in: iter_0
- description: The executor sometimes completes or partially completes reasoning about the task but terminates without producing the required deliverable file at the exact requested location. This manifests as an empty output inventory (no file created) and no file-writing action before end_turn. In this domain, that means failing to write the harmonized CSV (e.g., `/root/ckd_lab_data_harmonized.csv`) after cleaning, unit conversion, and formatting.
- latest_executor_action: Treat deliverable persistence as a mandatory final gate. Before end_turn: (1) run the full harmonization pipeline, (2) write the output to the exact required path/name, and (3) immediately verify the file exists, is non-empty, loads as a dataframe, has the expected columns/rowcount constraints, and meets formatting constraints (e.g., fixed-point `X.XX`, no scientific notation `e`, no thousand separators `,`). If any check fails, fix and re-save; do not end.
- remedy_log:
  - iter_0 | diagnosis: rollout ended without creating the required output file; no file-writing step executed
            | patch: record pattern and propose adding an explicit “persist + post-save verify” end-of-task gate to SKILL L2
