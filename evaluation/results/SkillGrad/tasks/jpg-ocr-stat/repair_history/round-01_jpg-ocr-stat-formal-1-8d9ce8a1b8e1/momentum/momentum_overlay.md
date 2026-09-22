### [jpg-ocr-stat] missing required Excel output artifact (no file created)
- signal: failure
- pattern: output-contract-excel-deliverable
- anchor: (none)
- gap: The run terminates without executing the required write step for `/app/workspace/stat_ocr.xlsx`, so there is no saved workbook to grade. The workflow lacks (or did not follow) a mandatory finalization step that treats the deliverable spec as a hard contract: save to exact path, then re-open to validate sheet name `results` and the required 3-column schema.
- proposed_change: Add a workflow rule (new L2 section in the most relevant skill, likely `xlsx` or a shared workflow header) requiring: (1) always write the output workbook to the exact required path; (2) re-open the file and validate sheet count/name, column headers/order, and any ordering constraints (e.g., sort by filename) before terminating; (3) if validation fails, fix and re-export.

## WORKFLOW-THEMES

- (none this iteration)
