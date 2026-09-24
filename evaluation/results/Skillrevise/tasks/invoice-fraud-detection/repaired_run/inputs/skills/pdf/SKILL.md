# Invoice PDF Fraud Detection (PDF + XLSX + CSV) Pipeline

## Purpose
Extract invoice-relevant fields from PDF pages, reconcile them against vendor and purchase-order reference data (XLSX/CSV), and apply fraud rules with explicit precedence to output only flagged/suspicious invoices/pages.

## When to Use
Use when the task requires detecting suspicious invoices by combining (a) per-page extraction from one or more invoice PDFs and (b) validation/matching against external reference files such as vendors.xlsx and purchase_orders.csv (or similarly named XLSX/CSV). Do not use for general PDF editing (merge/split/rotate/watermark/forms) or for tasks that only need raw PDF text without cross-file validation.

## Procedure
- 1) Discover inputs and constraints (before any parsing decisions).
- Locate candidate PDF(s) and reference XLSX/CSV files in the workspace; if multiple candidates exist, select by filename hints (invoice, vendor, po) and confirm by peeking at first rows/pages.
- Inspect reference files to discover columns and semantics (do not assume column names). Record:
- Vendor identity fields (name, alias, vendor_id) and bank fields (IBAN/account).
- Purchase order identifiers and amounts/currencies (if present).
- Checkpoint: if any required reference file is missing or columns are ambiguous, pause and request clarification rather than guessing.
- 2) Define a page-level extraction schema and normalizers.
- For each PDF page, target a minimal structured record:
- page_index_1_based, invoice_number, invoice_date, vendor_name, vendor_address (optional), iban/account, po_number, currency, total_amount.
- Create normalization rules:
- Trim whitespace; collapse repeated spaces.
- Money: parse to Decimal using locale-tolerant patterns (comma/period thousands/decimals). Keep the original string alongside the parsed Decimal if possible.
- IDs (invoice/PO): strip non-alphanumerics only if it improves match; keep raw value too.
- 3) Extract text from PDF with bounded fallback (page-scoped).
- Primary extraction: attempt text extraction per page using an available library/tool (prefer one already installed; discover availability first).
- Per-page completeness check: if extracted text is empty or missing key anchors (vendor name, total, PO/IBAN) then for that page only:
- Retry with alternate extraction settings/mode (for example, layout-preserving extraction or different tokenization).
- If still insufficient and the page appears scanned (very low text length), run OCR for that page only.
- Checkpoint: maintain a per-page note of which method succeeded; do not OCR the whole document unless the majority of pages fail.
- 4) Parse fields from extracted page text using patterns plus guardrails.
- Use multiple regex/pattern candidates per field (for example, "Invoice No", "Inv #", "Total", "Amount Due", "IBAN") and choose the best match by proximity to the label and reasonableness checks.
- Guardrails:
- Do not fabricate values. If not confidently found, set field to null/empty.
- Do not default missing amounts to 0.00.
- If multiple totals are found, prefer the one labeled as total/amount due over subtotals/tax, and record ambiguity if unresolved.
- 5) Reconcile against vendors and purchase orders (discovery-driven matching).
- Vendor matching:
- Compute a fuzzy match between extracted vendor_name and vendor reference names/aliases.
- Use a defined threshold and tie-break: if best and second-best are too close or below threshold, mark vendor as ambiguous (do not force a match).
- Independently compare IBAN/account (after normalization) to vendor bank fields when present; treat bank match as stronger evidence than name match alone.
- PO matching:
- If po_number exists, match against PO reference keys after normalization.
- If PO amount exists in reference data, compare totals using Decimal with a small tolerance only if the task specifies it; otherwise require exact match.
- 6) Apply fraud rules with explicit precedence and produce flagged output only.
- Establish rule precedence (highest to lowest) exactly as specified by the task; if unspecified, do not invent a precedence and ask.
- Evaluate rules per page using only available (non-null) fields; missing fields should generally yield "cannot evaluate" rather than "pass/fail" unless the rule explicitly treats missingness as suspicious.
- Output only pages/invoices that trigger at least one fraud rule, including:
- 1-based page index, extracted fields used by the rule, matched vendor/PO evidence (or ambiguity), and the single highest-precedence rule that caused flagging (plus any secondary triggered rules if required).
- Final checkpoint (execution anchor): spot-audit at least one flagged and one unflagged page to confirm (a) 1-based indexing, (b) Decimal parsing/comparisons, and (c) rule precedence correctness.

## Constraints / Pitfalls
- Never hard-code file paths, worksheet names, or column names; always discover them from the actual XLSX/CSV headers before matching.
- Do not coerce missing/uncertain fields into valid values (especially totals and PO numbers). Missingness must not silently flip a fraud decision; instead mark the page as "unknown/ambiguous" unless the rule explicitly flags missing data.