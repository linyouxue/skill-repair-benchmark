### output-contract-excel-deliverable | workflow | ensure required output artifact is written to exact path with required schema and validated before termination
- anchor: (none yet)
- appeared_in: iter_0
- description: The executor may complete intermediate reasoning (e.g., OCR, parsing) but fail to create any output artifact, or create one at the wrong location/schema. This presents as an empty output inventory and a run ending "stuck" without a final save step. For deliverables like an Excel workbook, the contract includes: exact file path, sheet name(s), required columns, ordering constraints, and absence of extras.
- latest_executor_action: Treat the deliverable spec as a hard output contract. Before ending the run: (1) write the artifact to the exact required path; (2) immediately re-open/inspect it to validate existence, sheet name/count, column headers and order, and any required row ordering; (3) if any check fails, fix and re-export (do not continue iterating on upstream steps while the output contract is unmet).
- remedy_log:
  - iter_0 | diagnosis: No output artifact was produced; required /app/workspace/stat_ocr.xlsx (sheet "results" with 3 columns) was never written or validated before termination
            | patch: record new workflow rule to add a mandatory output-contract step for Excel deliverables; suggest adding/strengthening a guidance anchor covering save + re-open validation
