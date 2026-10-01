### [bike-rebalance] missing required output file `report.json`
- signal: failure
- pattern: output-commit-report-json
- anchor: output-commit-write-the-deliverable
- gap: The run terminated without any file-generation action for `report.json`; output inventory contained only `data.json`, so the verifier had nothing to validate. The existing guidance emphasizes modeling/validation, but the “output commit” phase was not executed as a hard gate before termination.
- proposed_change: Strengthen the `scip-opt` L2 section `## Output Commit (Write The Deliverable)` into an explicit termination guard/checklist: before `end_turn`, assert `Path("report.json").exists()` and `json.loads(...)` succeeds, then re-run required-keys + entity-coverage checks per `scip-opt/references/output-commit-report-json.md`. If optimization is incomplete, still assemble and write a minimal feasible `report.json` (heuristic routes/zero moves) rather than ending with no file.

## WORKFLOW-THEMES

- (none this iteration)
