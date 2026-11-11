# PDF-to-Data Extraction and Verified Output

## Purpose
Extract text and simple tables from PDFs in a tool-constrained execution environment, optionally combine with spreadsheet data, and produce verifier-aligned output artifacts with explicit existence/readability checks.

## When to Use
Use this skill when the task requires reading a PDF (rules, spec, report, or embedded tables) and turning it into structured text/data for downstream computation, especially when the environment enforces strict command execution (one command per tool call unless explicitly chained) and a verifier expects an output file at an exact path.

## Procedure
- 1) Discover inputs and constraints (no assumptions)
- List available files in the working directory and identify candidate PDFs/spreadsheets.
- If the task/verifier specifies an output path (for example /root/answer.txt), record it exactly; otherwise choose an output path only after confirming a writable directory.
- Check tool availability by attempting minimal imports (pypdf, pdfplumber, pandas) using a single Python invocation.
- 2) Choose an extraction route (decision point)
- If you need plain text and layout is not critical: prefer pypdf text extraction.
- If layout or tables matter: prefer pdfplumber.
- If imports fail, fall back to command-line utilities only if they are present (for example pdftotext); discover by running the tool with a help/version flag.
- 3) Extract minimally, then validate evidence (checkpoint)
- Run the smallest extraction that proves progress (for example: page count, first 200 characters of page 1, or table row counts).
- Evidence to collect before heavier processing:
- Number of pages extracted successfully.
- Non-empty text sample or non-empty table output for at least one page.
- If evidence is empty, reassess: the PDF may be scanned (image-only). Only then consider OCR as an explicit alternative, and validate that OCR tools are installed before proceeding.
- 4) If spreadsheets are involved, load with discovery-first parsing (optional)
- Use pandas to enumerate sheet names and inspect headers (read a small sample) before assuming column names or data types.
- Validate row/column counts and print a small preview as evidence before computing final results.
- 5) Produce required outputs and verify at the exact path (final checkpoint)
- Write outputs only after confirming the destination directory is writable.
- Immediately verify the artifact at the exact required path using a separate existence + read check (for example: list the file and print the first lines).
- Do not stop until the verifier-visible check succeeds.
- 6) Bounded recovery after tool failure (single fallback branch)
- If any tool call fails (for example: "cannot execute multiple commands at once" or an import error):
- Re-run the smallest failing action as a single command only (or explicitly chain with && in one shell command).
- Re-run only the minimal validation check (page count/text sample/file existence) to confirm recovery.
- If the same failure repeats, switch to the closest supported alternative (library <-> CLI) and retry the minimal check once; then stop and request clarification if requirements are ambiguous.

## Constraints / Pitfalls
- One-command rule: never submit multiple independent commands in one tool call unless explicitly chained with && or ; in a single shell command. Prefer separate tool calls for "run then verify" steps.
- Verifier alignment: never assume an output was created; always perform an explicit existence/readability check at the exact task-specified path before finishing. Avoid writing to alternate locations unless the task allows it and you can prove the verifier will read it there.