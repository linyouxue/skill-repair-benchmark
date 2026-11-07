# Rulebook-Driven Tabular Scoring

## Purpose
Reusable procedure for tasks that combine a rulebook document (PDF or similar) with a tabular dataset (xlsx, csv, or equivalent) to compute a scored or matched numeric answer. Covers extraction, input validation, rule interpretation with sensitivity testing, and verification. Standalone PDF authoring, OCR, and form filling remain out of scope and delegate to sibling skills.

## When to Use
Trigger when a task provides (a) a rules or scoring document and (b) a structured dataset of events, turns, rows, or records, and asks for an aggregate numeric result (score, count, match total, ranking). Also use when a PDF alone drives a downstream computation. Do not use for pure extraction tasks with no downstream reasoning; a lighter extraction skill suffices there.

## Procedure
- Discover and extract: identify input files and their formats. For PDFs, try extractors in order pdfplumber, pypdf, pdftotext (CLI with `-layout`); install only if none are present. For spreadsheets, prefer pandas/openpyxl. Record the chosen backends. If the PDF sample is empty, stop and escalate to an OCR-capable sibling skill.
- Validate inputs: load the tabular dataset and print observed row count, column count, index/key range, and any null cells. Derive the expected shape from the rulebook (for example, N turns per game, M games). Assert observed vs expected; if there is a gap (missing row, duplicate key, out-of-range value), halt scoring and move to the gap-handling step before any aggregation.
- Quote rules verbatim: for every scoring category, definition, threshold, or tie-breaker, copy the exact sentence from the rulebook into an Assumptions block. Do not paraphrase before quoting. Record page or section anchors so a reviewer can re-locate each quote.
- Interpret and sensitivity-test: for each quoted rule, write an Interpretation block with (1) the verbatim quote, (2) two or more candidate readings whenever wording is ambiguous (for example contiguous vs any-order sequences, exactly-K vs at-most-K distinct values, inclusive vs exclusive bounds), (3) the chosen reading with explicit textual justification, and (4) the score delta if the alternative reading were used. If the delta changes the final answer and the text does not clearly favor one reading, surface the ambiguity rather than committing silently.
- Handle data gaps explicitly: when validation found missing or malformed rows, enumerate at least two documented policies (for example: score only available sub-records, treat missing sub-records as zero, drop the parent record entirely). Pick one with a stated reason, and recompute the final answer under each policy as a sensitivity check. Report the chosen policy alongside the answer.
- Compute and verify: implement scoring as per-category pure functions over the validated table, sum per the rulebook's aggregation, and reload the written artifact (if any) to re-read and re-assert required fields, types, and ranges before finalizing.

## Constraints / Pitfalls
- Do not silently impute missing rows, cells, or categories. Every gap must be surfaced with counts and resolved by an explicitly chosen, documented policy.
- Do not paraphrase rulebook text before quoting it; interpretations live next to the quote, never in place of it.
- Do not commit to a single interpretation of ambiguous wording without a sensitivity delta; if the delta flips the answer and the text is ambiguous, report both candidates.
- Do not expand this skill into PDF authoring, OCR, encryption, watermarking, or form filling; delegate those to sibling skills.
- Keep all output in printable ASCII unless the source explicitly requires other characters. Record the chosen extractor and spreadsheet backend in the output notes.