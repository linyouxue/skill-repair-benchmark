### [manufacturing-equipment-maintenance] ended run without writing required /app/output/q01.json…q05.json deliverables
- signal: failure
- pattern: write-required-output-artifacts
- anchor: write-required-output-artifacts-do-not-end-with-empty-inventory
- gap: The run terminated at end_turn without any tool actions that materialized the required JSON files under /app/output/ (q01–q05) and without the pre-termination existence/parse/schema guard. The skill already specifies “Only terminate after writing all required artifacts and verifying they exist and parse,” but the executor did not execute a dedicated “write outputs then validate” phase.
- proposed_change: Strengthen L2 “Write required output artifacts (do not end with empty inventory)” into an explicit end-of-run checklist that must be executed immediately before end_turn (write placeholders early; overwrite with computed answers; then run validate_required_files and hard-fail if problems != []). Add a short pointer in L2 to references/output-artifact-protocol.md emphasizing that validation is a blocking gate, not optional.

## WORKFLOW-THEMES

- (none this iteration)
