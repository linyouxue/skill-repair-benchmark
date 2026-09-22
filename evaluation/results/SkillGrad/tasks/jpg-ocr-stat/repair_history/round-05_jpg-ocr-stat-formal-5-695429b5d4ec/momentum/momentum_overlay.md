### [jpg-ocr-stat] workbook written to wrong location; required /app/workspace/stat_ocr.xlsx missing
- signal: failure
- pattern: output-contract-excel-deliverable
- anchor: deliverable-contract-save-validate-before-ending
- gap: The run appears to have produced an .xlsx, but not at the exact mandated absolute path `/app/workspace/stat_ocr.xlsx` (e.g., saved to a relative `workspace/...` path or another working directory). The executor did not perform a post-save existence check against the contract path, so it ended while the harness still saw the deliverable as missing.
- proposed_change: Strengthen L2 xlsx "Deliverable-first control loop" + "Termination guardrail" to explicitly forbid relative-path substitutions: (1) restate contract as an absolute path; (2) use `Path(contract_path)` and `out_path.parent.mkdir(..., exist_ok=True)`; (3) after `to_excel`/`wb.save`, assert `out_path.exists()` and optionally `out_path.resolve() == Path(contract_path)`; (4) if missing, immediately re-save to the contract path and re-open/validate per references/output-contract-excel.md.

## WORKFLOW-THEMES

- (none this iteration)
