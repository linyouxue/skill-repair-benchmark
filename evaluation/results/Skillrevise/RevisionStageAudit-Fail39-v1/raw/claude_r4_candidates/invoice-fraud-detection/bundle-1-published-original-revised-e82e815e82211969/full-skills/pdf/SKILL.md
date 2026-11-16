# Structured PDF Reconciliation

## Purpose
Reusable workflow for tasks that cross-reference fields extracted from invoice-like PDFs against structured reference tables (vendors, POs, ledgers) and emit a JSON report applying a task-declared rule precedence.

## When to Use
Trigger: the task provides a set of semi-structured PDFs plus one or more reference tables (CSV/JSON) and asks for per-document classification, flagging, or matching against those tables, with an output schema and rule precedence declared by the task. Do not use for pure PDF manipulation (merge, split, rotate, OCR, form filling).

## Procedure
- Discover inputs: list the PDF directory and reference files; read the task statement for the exact output path, JSON schema, rule precedence, and indexing base (0 vs 1). Record these verbatim; do not guess.
- Choose extractor: use pdfplumber `page.extract_text()` as default. If text is empty or garbled on a sample page, fall back to `extract_words()` with layout, or `pdftotext -layout` if available. Print one parsed-field dict from a sample document to confirm label:value patterns before scaling up.
- Parse fields: write label-anchored patterns (e.g., `From:`, `IBAN:`, `PO:`, `Total:`) tolerant to whitespace and casing; set missing fields to `null`, not `""`. Normalize vendor names (lowercase, strip punctuation, collapse whitespace) and IBAN/PO (remove spaces, uppercase) consistently on both PDF and reference sides.
- Join and classify: match against reference tables using normalized keys first (exact), then a calibrated fuzzy fallback. Calibrate the fuzzy threshold on a few known-good vendor pairs; prefer accepting a match unless the best score is both low and clearly separated from the next candidate. Apply the task's rule precedence in the declared order; assign only the first matching reason per record.
- Emit and verify: write the JSON to the task-specified path. Then reload the file, assert required keys/types and indexing base match the schema, and print per-reason counts. If any single reason dominates (e.g., >50% of records), re-inspect parsing and matching before finalizing.

## Constraints / Pitfalls
- Honor the task's rule precedence literally; do not reorder or merge reasons.
- Do not hard-code thresholds, field names, file paths, or vendor lists; derive them from inputs and task text.
- Use `null` (not empty string) for missing optional fields such as PO.
- Preserve the task's indexing convention (page/row 0-based vs 1-based); verify on a known record.
- Prefer "matched" over "Unknown Vendor" when fuzzy scores are close; isolated low scores with no near-neighbor are stronger evidence of a real mismatch.
- Keep the skill focused on reconciliation; defer generic PDF manipulation to other tooling.