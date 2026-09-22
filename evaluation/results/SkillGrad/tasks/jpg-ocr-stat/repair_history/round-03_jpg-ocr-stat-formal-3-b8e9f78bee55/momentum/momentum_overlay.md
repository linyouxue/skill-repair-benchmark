### [jpg-ocr-stat] Missing required output workbook at /app/workspace/stat_ocr.xlsx
- signal: failure
- pattern: output-contract-excel-deliverable
- anchor: deliverable-contract-save-validate-before-ending
- gap: The run terminated ("end_turn") without ever creating and saving the required deliverable workbook to `/app/workspace/stat_ocr.xlsx`. This violates the xlsx/SKILL.md "Deliverable-first control loop" decision rule: "if you have made several tool calls without creating the deliverable file, stop exploring and immediately write the skeleton workbook, then proceed." There was also no post-save re-open validation (existence, only `results` sheet, exact headers/order).
- proposed_change: Strengthen the deliverable-first guidance at `deliverable-contract-save-validate-before-ending` to include a hard trigger like: "By step N (or after N tool calls), you MUST have written `/app/workspace/stat_ocr.xlsx` skeleton (sheet `results`, headers `filename,date,total_amount`) and re-opened it to confirm." Add an explicit pre-termination checklist: (1) file exists at exact path; (2) sheet set exactly `["results"]`; (3) headers exactly `["filename","date","total_amount"]`; (4) rows sorted by filename.

## WORKFLOW-THEMES

- (none this iteration)
