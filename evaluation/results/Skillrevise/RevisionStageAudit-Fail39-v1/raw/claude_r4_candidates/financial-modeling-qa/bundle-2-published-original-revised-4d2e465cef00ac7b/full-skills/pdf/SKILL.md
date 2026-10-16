# PDF Text and Table Extraction

## Purpose
Reusable procedure for extracting text and tables from PDF documents in environments where the available extractor is not known in advance. Scope is limited to extraction and form-fill delegation; spreadsheet, financial, or rulebook reasoning belongs to a different skill.

## When to Use
Trigger when a task requires reading content out of a PDF file (plain text, layout-preserved text, or tabular data), or when a PDF rulebook feeds a downstream computation. For PDF form filling, delegate to the forms-specific sibling skill. Do not use this skill as a general PDF authoring, OCR, encryption, or watermarking manual.

## Procedure
- Discover: probe the environment before committing to a tool. Run `which pdftotext`, then `python -c "import pdfplumber"` and `python -c "import pypdf"`. Pick the first available in order: pdfplumber (text and tables), pypdf (simple text and page ops), pdftotext (CLI, layout mode with `-layout`). If none are present, attempt `pip install pdfplumber pypdf`; if PEP 668 blocks it, retry with `--break-system-packages` or a venv, and record which route succeeded.
- Extract: run the chosen backend against the target file. For tables prefer pdfplumber `page.extract_tables()`; for layout-sensitive text prefer `pdftotext -layout`. Capture page count and a short sample first to confirm the PDF is text-based rather than scanned; if sample is empty, stop and escalate to an OCR-capable sibling skill rather than guessing.
- Quote: when the extracted text contains rules, definitions, thresholds, or scoring logic that will drive a downstream numeric answer, write an Assumptions block that quotes each relevant sentence verbatim and states the interpretation derived from it. Do not paraphrase before quoting.
- Verify: reload the written artifact or re-read the extracted text and assert that required sections, headers, or table shapes are present. If a downstream computation depends on the extraction, cross-check with a second backend on at least one page before finalizing.

## Constraints / Pitfalls
- Do not assume any extractor is installed; always discover first and fall back along the documented order. Record the chosen backend in output.
- Do not silently drop rows, pages, or table cells. If extraction yields fewer rows or pages than expected, stop and surface the anomaly with counts rather than imputing.
- Do not invent scoring rules, category definitions, or run definitions when extracting from a rulebook. Quote verbatim; if the source is ambiguous, emit the ambiguity alongside any numeric answer.
- Do not expand this skill into authoring, merging, splitting, OCR, watermarking, or encryption. Those belong to separate skills.
- Keep all output in printable ASCII unless the source PDF explicitly requires other characters.