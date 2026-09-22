### [reserves-at-risk-calc] Output artifact not delivered (/root/output/rar_result.xlsx missing)
- signal: failure
- pattern: save-and-verify-output-artifact
- anchor: workflow-deliver-the-required-artifact-mandatory
- gap: The run terminated (“end_turn”) without executing the mandatory completion gate from **Workflow: Deliver the required artifact (mandatory)**—no step that saves/exports the workbook to the exact required path (/root/output/rar_result.xlsx) and then verifies the file exists. Output inventory contained only an input/template workbook, consistent with never writing the final deliverable.
- proposed_change: Strengthen executor adherence to the L2 completion gate by making it an explicit last-step checklist item that must be performed immediately before end_turn: (1) save to the exact required output path/filename, (2) `Path.exists()` check, (3) if missing, retry save after creating parent dirs. Consider adding a one-line “STOP: do not end until out_path.exists() is true” guard to the end of the workflow section.

## WORKFLOW-THEMES

- (none this iteration)
