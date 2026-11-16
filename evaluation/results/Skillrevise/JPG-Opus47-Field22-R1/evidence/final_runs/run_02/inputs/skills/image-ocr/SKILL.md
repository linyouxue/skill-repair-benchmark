# Receipt OCR to XLSX

## Purpose
Extract per-receipt `date` (ISO `YYYY-MM-DD`) and `total_amount` (string with exactly two decimals) from a directory of scanned receipt images and write a single-sheet xlsx whose path, sheet name, column order, and null semantics are given by the task prompt.

## When to Use
Trigger only when the task supplies a directory of receipt images and requests a tabular file of per-receipt date and total. Do not use for generic OCR, PDFs, video frames, or captioning.

## Procedure
- Discover: read the input image directory and output xlsx path from the task prompt. List `*.jpg/*.jpeg/*.png` sorted ascending by filename; record N.
- OCR with multiple variants per image, keeping line structure. Start with default and grayscale+autocontrast. If no priority-tier candidate is found, or if the chosen total disagrees with every anchor, escalate: try upscales (e.g. 2x and 3x) and alternate PSMs (e.g. 4, 6, 11) until a candidate is confirmed by an anchor or the small variant set is exhausted.
- Extract date candidates per pass: match `DD[/-]MM[/-]YYYY`, `DD[/-]MM[/-]YY` (YY -> 20YY), `YYYY-MM-DD`, `DD Mon YYYY`; validate `1<=month<=12`, `1<=day<=31`. Select the token on a line containing a `Date`/`Tarikh`/`Tanggal` label if any pass yields one; parse that exact token with day-first ordering only when the first field is `<=12` fails to disambiguate (i.e. keep printed DD/MM order). If no labelled candidate validates, fall back to the earliest valid non-time-adjacent date appearing in `>=2` passes; else None.
- Extract total candidates per pass by scanning tier keywords in task-hint priority order on non-excluded lines (exclusions: SUBTOTAL, SUB TOTAL, TAX, GST, SST, DISCOUNT, CHANGE, CASH TENDERED, plus any line whose keyword follows a payment/tender/card/change/received token). Number pattern allows comma thousands and two decimals; strip commas. If a tier line itself has no decimal number, use the last number on the next non-excluded line.
- Build an anchor set A from the same OCR text: Subtotal, Total Incl GST, Rounded/Net/Total Rounded, abs(Payment/Visa/Mastercard/Cash) only when the line does not match Change/Tendered, and (Cash - Change) when both present.
- Reconcile total:
- Pick the highest-priority tier that produced any candidate.
- Within that tier, drop any candidate whose leading integer digit disagrees with every anchor's leading digit, or whose value exceeds `2x` the maximum anchor.
- If a Rounding/Rounded/Rounding Adj line separates two candidates, prefer the later line's value (final post-rounding total).
- Among survivors, prefer a value equal (within 0.05) to any anchor; else the value appearing in the most passes; else the earliest occurrence.
- If no tier candidate survives but `>=2` anchors agree within 0.05, emit that anchor value. Otherwise emit None.
- Write xlsx with openpyxl: one sheet `results`; header `['filename','date','total_amount']`; one row per image in filename order; use Python `None` for nulls.
- Validate and finalize (execution anchor): reopen the xlsx, iterate every data cell, coerce `''` and whitespace-only values to `None`, re-save. Reload and assert: `sheetnames == ['results']`; header matches; row count `== N`; every non-null date matches `^\d{4}-\d{2}-\d{2}$`; every non-null total matches `^\d+\.\d{2}$`; no cell equals `''`. If any assertion fails, fix in place and re-assert before terminating.

## Constraints / Pitfalls
- Never emit an empty string; nulls must be Python `None`. The post-write reload-and-assert step is mandatory, not advisory.
- Do not let anchor-equality override an explicit higher-priority tier match except via the leading-digit / 2x-anchor outlier filter in step 6.
- Do not fall through next-line to any payment/cash/card/change/tender/rounding line, regardless of exact phrasing.
- Do not hardcode paths, filenames, PSM/scale values, or per-image literals; all paths come from the task prompt and OCR variants are chosen by the escalation ladder.
- Do not add extra sheets, columns, or rows; do not write confidence or metadata artifacts.