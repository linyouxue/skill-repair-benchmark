### [jpg-ocr-stat] run ended without producing required /app/workspace/stat_ocr.xlsx workbook
- signal: failure
- pattern: output-contract-excel-deliverable
- anchor: deliverable-contract-save-validate-before-ending
- gap: The agent terminated early after only 2 tool calls and no skill invocations, never executing the OCR→parse→XLSX pipeline and never writing the required deliverable to `/app/workspace/stat_ocr.xlsx`. The existing xlsx guidance contains a hard trigger to "save a skeleton workbook by ~3 tool calls" and "do not end the run until the re-open checks pass", but the executor still issued `end_turn` while the output file was missing.
- proposed_change: In L2 at anchor `deliverable-contract-save-validate-before-ending`, add an explicit termination guardrail: (1) forbid `end_turn` if `out_path` does not exist; (2) enforce a step-count trigger: by tool call 3 (or immediately after reading the contract), write a skeleton workbook at the exact path (sheet `results`, columns `filename,date,total_amount`) and re-open validate; (3) add a short pre-end checklist item that must be satisfied verbatim (exists, single sheet name match, header order match) before stopping.

## WORKFLOW-THEMES

- (none this iteration)
