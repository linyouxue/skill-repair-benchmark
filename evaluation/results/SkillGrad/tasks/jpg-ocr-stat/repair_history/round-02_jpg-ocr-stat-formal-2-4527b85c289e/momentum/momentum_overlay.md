### [jpg-ocr-stat] iteration budget exhausted before producing required Excel deliverable
- signal: failure
- pattern: output-contract-excel-deliverable
- anchor: deliverable-contract-save-validate-before-ending
- gap: No output workbook was produced; run ended with `MaxIterationsReached` after looping tool calls and `n_skill_invocations: 0`, so it never entered the expected workflow (enumerate images → OCR batch → parse fields → write `/app/workspace/stat_ocr.xlsx` and re-open validate).
- proposed_change: Add an explicit skill-level control policy at anchor `deliverable-contract-save-validate-before-ending`: (1) after reading prompt, immediately restate deliverable contract (path `/app/workspace/stat_ocr.xlsx`, sheet `results`, columns `date | total | file_name`), (2) enforce an early-plan-then-execute checklist and invoke `image-ocr` (or `openai-vision`) + `xlsx` in a straight-line pipeline, and (3) add a hard cap on exploratory tool calls—if the workbook has not been created by step N, force immediate creation with best-effort parsing and nulls, then validate by re-opening.

## WORKFLOW-THEMES

- (none this iteration)
