# Pattern record

### persist-required-deliverables | workflow | ensure required output artifact is written to the specified path and verified before termination
- anchor: step-4-persist-deliverable-post-save-verification
- appeared_in: iter_0, iter_1, iter_2
- description: The executor sometimes completes or partially completes reasoning about the task but terminates without producing the required deliverable file at the exact requested location. This manifests as an empty output inventory (no file created) and no file-writing action before end_turn. In this domain, that means failing to write the harmonized CSV (e.g., `/root/ckd_lab_data_harmonized.csv`) after cleaning, unit conversion, and formatting.
- latest_executor_action: Treat deliverable persistence as a mandatory final gate. Before end_turn: (1) run the full harmonization pipeline, (2) write the output to the exact required path/name via `df.to_csv(out_path, index=False)`, and (3) immediately verify the file exists and is non-empty, then round-trip re-load it and assert schema/format expectations (at least: `list(check.columns) == list(df.columns)`). If any check fails, fix the pipeline/output formatting and re-save; do not end.
- remedy_log:
  - iter_0 | diagnosis: rollout ended without creating the required output file; no file-writing step executed
            | patch: record pattern and propose adding an explicit “persist + post-save verify” end-of-task gate to SKILL L2
  - iter_1 | diagnosis: run finished without producing `/root/ckd_lab_data_harmonized.csv`; agent terminated (end_turn) without any write-to-disk step
            | patch: map the failure to existing SKILL.md Step 4 and strengthen the completion gate expectation in the pattern record (explicitly “do not end before round-trip verification”).
  - iter_2 | diagnosis: end_turn occurred with no new artifact in output inventory; executor skipped Step 4 persistence + post-save verification despite rule being present
            | patch: (pending) reinforce as a non-skippable termination gate (e.g., add an explicit “before end_turn, confirm output_path exists via Path.exists() and reload” checklist item in executor workflow / termination policy).
