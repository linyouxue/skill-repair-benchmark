# PDF-Driven Record Reconciliation

## Purpose
Provide a reusable workflow for tasks that extract structured records (for example invoices, receipts, statements) from PDF documents and cross-reference them against one or more reference datasets (vendors, purchase orders, price lists) to detect anomalies or produce a filtered report. The skill focuses on extraction-plus-join-plus-rule-check, not on generic PDF manipulation.

## When to Use
Use this skill when the task provides (a) one or more PDFs whose pages carry repeatable record fields and (b) auxiliary reference tables, and asks for a structured output (usually JSON) that flags, filters, or classifies pages according to task-declared rules. Do not use it for pure PDF manipulation (merging, watermarking, form filling, OCR-only jobs) where no reference data or rule engine is involved.

## Procedure
- Discover inputs and contract. List all provided files and their types. Read the task statement to extract: required output path, output schema (keys, types, nullability), page-indexing convention (default 1-based unless stated), amount tolerance (default Decimal 0.01 unless stated), rule set, and rule precedence. Record these in a short run log before writing any code.
- Probe one page end-to-end. Pick one PDF page, extract text with pdfplumber (layout-aware); if fields are empty, fall back to pdfplumber with `layout=True` or to pypdf; if the page is image-only, fall back to OCR (pdf2image + pytesseract). Confirm you can parse every schema-required field from this page before scaling up. Do not proceed until a single page round-trips cleanly.
- Load reference tables with explicit types. Use pandas or csv; coerce monetary amounts to `decimal.Decimal`, dates to ISO, identifiers to stripped strings. Build lookup indices (dict by normalized key) rather than relying on linear scans.
- Resolve vendors and POs with calibrated matching. Normalize names once (lowercase, collapse whitespace, strip legal suffixes like "inc", "llc", "ltd", punctuation). Prefer exact normalized match. For fuzzy matching use rapidfuzz (or difflib as fallback); do NOT hard-code a similarity threshold. Instead, print the top-k candidates and scores for a sample of borderline cases, and choose a rule that errs toward "vendor exists" so that downstream amount/PO checks can run. Record the chosen rule in the run log.
- Apply fraud or anomaly rules in declared precedence. Evaluate each rule in the exact order given by the task; assign the first matching reason only. Compare monetary values with `Decimal` and the task-declared tolerance. Treat missing optional fields (for example PO number) as `null`, not as a violation, unless the task says otherwise.
- Emit output and validate. Write only records that match the task's inclusion rule (commonly: only flagged items). Use 1-based page indices unless the task states otherwise. Then reload the written file, assert every required key is present with the right type, and print a summary: total pages, flagged count, and per-reason counts. If the flagged ratio looks implausible (for example >80% flagged with no supporting rule rationale), stop and re-examine normalization and matching before declaring completion.

## Constraints / Pitfalls
- Do not invent thresholds, schemas, or precedence rules; derive every parameter from the task statement or from an explicit calibration step logged in the run.
- Use `decimal.Decimal` for all monetary comparisons; never compare floats directly. Default tolerance is 0.01 unless the task overrides it.
- Preserve the task-declared rule precedence exactly; assign one reason per record (the first matching one).
- Page indexing is 1-based by default; verify against the task before emitting.
- Output must contain only the records the task asks for (typically flagged only), with no extra keys beyond the declared schema.
- Fallbacks are bounded: text -> layout mode -> OCR for extraction; exact-normalized -> fuzzy-with-calibration for matching. Do not expand into generic troubleshooting.
- Treat missing optional fields as `null`, not as evidence of fraud, unless the rule set explicitly says so.
- The post-write reload-and-assert step is mandatory; a run that cannot reload and validate its own output is not complete.