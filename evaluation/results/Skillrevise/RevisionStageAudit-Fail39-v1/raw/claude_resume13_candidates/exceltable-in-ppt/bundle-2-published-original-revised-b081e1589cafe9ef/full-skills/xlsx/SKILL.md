# xlsx (standalone and embedded in Office containers)

## Purpose
Create, edit, analyze, and ship .xlsx files reliably, including when the xlsx is embedded inside a pptx or docx container. The skill emphasizes preserving formulas during edits, refreshing cached formula values before delivery, and keeping container files byte-faithful outside the intended change.

## When to Use
Use when a task requires producing or modifying an xlsx artifact, or modifying an xlsx that is embedded as an OLE part inside a pptx/docx (for example, under ppt/embeddings/ or word/embeddings/). The reusable trigger is: a verifier will open an xlsx (directly or inside a container) and read both input cells and formula results.

## Procedure
- Discover
- Inspect inputs. If the target is a pptx/docx, list its zip members and locate embedded xlsx parts under paths matching `*/embeddings/*.xlsx` (and `.xlsm`). Note member order and ZipInfo for later repack fidelity.
- If target is a standalone xlsx, skip container steps.
- Probe tooling actually available: locate the recalc helper (e.g., `recalc.py`) via `find` or `which`; probe for a headless spreadsheet engine (LibreOffice `soffice`, or equivalent). Do not assume a fixed path.
- Validate
- Open the xlsx (extract from the container to a temp path first if embedded) with `openpyxl.load_workbook(..., data_only=False)` to preserve formula strings.
- Record the set of formula cells and the set of cells the task will modify. Compute the dependency closure (any formula whose referenced range intersects an edited cell) so you know which cached results must be refreshed.
- Confirm the planned edit does not overwrite a formula cell with a literal unless the task explicitly requires it.
- Edit
- Apply only the required cell changes. Keep formula strings intact. Do not re-apply formatting or touch unrelated sheets, defined names, or styles.
- Save to a new path; never save over the original until repack is verified.
- Recalc (MANDATORY whenever any edited cell is referenced by any formula, including inside embedded xlsx)
- Run the discovered recalc helper on the exact xlsx that will be shipped (the extracted embedded xlsx, not a copy left in the temp dir unused).
- Expected evidence: recalc returns `status: success` with `total_errors: 0`. If `errors_found`, fix the formula or input and rerun. Do not proceed on stale cache.
- Verify output contract
- Reload the recalculated xlsx with `data_only=True` and assert:
- edited cells hold the intended values and types,
- every formula in the dependency closure has a non-None, non-error cached value,
- no cell contains `#REF!`, `#DIV/0!`, `#VALUE!`, `#N/A`, `#NAME?`.
- Do not save after this read; `data_only=True` discards formulas on write.
- Repack (container case only)
- Rebuild the container by copying every original zip member byte-for-byte in original order, substituting only the modified embedded xlsx. Preserve each member's ZipInfo (compression type, external attrs, date_time) where possible.
- Verify: member name list and order match the source; for every non-target member, CRC and uncompressed size match the source. Only the edited embedding should differ.
- Write the final container to the required output path.
- Final check
- Reopen the final shipped file (container or xlsx) using the same path the verifier would use and repeat the data_only=True assertions on the embedded or standalone workbook.

## Constraints / Pitfalls
- Do not replace formulas with Python-computed literals. If a value is defined by a formula in the source, keep the formula and refresh its cached result via recalc.
- Do not ship an edited workbook without running recalc when any edited cell is a formula input. Cached results from the pre-edit state will mislead verifiers that read values rather than formulas.
- Do not open an existing workbook with `data_only=True` and then save it; this permanently loses formulas.
- Do not modify unrelated parts of a pptx/docx (slides, media, rels, previews) unless the task requires it. Preserve zip member order and metadata.
- Do not hard-code tool paths or versions. Discover `recalc.py` and the headless spreadsheet engine at runtime; if neither is available, stop and report rather than shipping an un-recalculated file.
- Do not encode task-specific cell addresses, expected numeric answers, or sheet names into this procedure; derive them from the task inputs each run.
- Keep edits minimal: the smaller the diff from the source container, the lower the risk of breaking unrelated verifier checks.