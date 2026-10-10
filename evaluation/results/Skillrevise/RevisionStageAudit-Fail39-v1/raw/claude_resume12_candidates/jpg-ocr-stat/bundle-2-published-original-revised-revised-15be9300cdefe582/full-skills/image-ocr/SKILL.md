# Receipts OCR to Structured Table

## Purpose
Convert a directory of receipt images into a single structured tabular artifact (e.g., XLSX/CSV) whose rows capture per-receipt fields such as filename, date, and total amount. Emphasize line-structure-preserving OCR, deterministic field parsing, and post-write schema validation at the task-declared output path.

## When to Use
Use when the task provides a set of receipt-like images and requires a tabular output file (XLSX or CSV) with a fixed sheet name and column schema. Do not use for free-form text extraction, document transcription, or when the deliverable is unstructured text/JSON.

## Procedure
- Discover contract from the task description: input image directory, exact output file path, sheet name, column order, and per-column format rules (e.g., ISO date, two-decimal string, nullability). Do not assume defaults; if ambiguous, inspect the task files and verifier before writing.
- Enumerate input images via glob of standard extensions in the given directory; sort by filename for deterministic row order.
- For each image: run OCR with a line-preserving configuration (default `--psm 6` on a grayscale + autocontrast variant). Persist the raw OCR text to a per-image cache file immediately so progress is incremental and resumable. Bound per-image OCR time; on timeout or exception, record empty text and continue.
- Parse fields from the cached line-structured text using explicit rules derived from the task spec, for example:
- Total: scan lines for a prioritized keyword list (e.g., TOTAL, AMOUNT DUE, GRAND TOTAL), apply an exclusion list (e.g., SUBTOTAL, GST SUMMARY, CHANGE), and fall back to the next line if the amount is not on the same line.
- Amount normalization: strip currency tokens, map OCR `O`/`o` to `0`, collapse spaced decimals (`86. 00` -> `86.00`), decide comma-as-thousands vs comma-as-decimal from locale/context, and format to the task-declared precision.
- Date: try a declared set of patterns, then normalize to ISO `YYYY-MM-DD`; on failure emit null, not a guess.
- Write the output file to the exact task-declared path, using the exact sheet name and column headers in the declared order, one row per input image.
- Validate before finalizing: reopen the written file; assert the output path exists, the sheet name matches, headers match exactly, row count equals image count, and each cell satisfies its declared type/format. Print a one-line `schema OK: <path> rows=<n>` on success; on any mismatch, fix and rewrite rather than claim completion.

## Constraints / Pitfalls
- Do not concatenate multi-pass OCR outputs for parsing; line structure must be preserved. If multiple passes are tried, parse each independently and pick per-field, not by text union.
- Do not invent an output schema. Use only the sheet name, column names, order, and formats declared by the task; no extra columns, sheets, or metadata.
- Do not redirect the output to a different path if writing fails; diagnose permissions/paths and write to the declared location.
- Never emit a plausible-but-unverified value when parsing fails; emit null (or the task-declared sentinel) and let the row be incomplete.
- Avoid single long synchronous OCR loops without per-image caching; otherwise the run can stall and leave no artifact.
- Keep field-parsing rules (keyword priority, exclusions, fallbacks, normalization) declared as data (lists/regex tables), not hard-coded to one dataset, so the skill transfers across receipt sets.
- The final step must be the post-write schema+existence check; completion may only be claimed after it passes.