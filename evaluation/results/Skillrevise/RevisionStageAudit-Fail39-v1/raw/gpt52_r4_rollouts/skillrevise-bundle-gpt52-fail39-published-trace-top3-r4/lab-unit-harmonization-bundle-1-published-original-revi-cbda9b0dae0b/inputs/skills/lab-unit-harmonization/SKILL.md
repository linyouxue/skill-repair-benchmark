# Lab Unit Harmonization (Discovery-Driven)

## Purpose
Harmonize laboratory measurements from mixed sources by (1) parsing messy numeric strings, (2) converting units only when a documented rule exists, and (3) validating the resulting dataset against an explicit, discovered contract (columns, types, and any required output format) before declaring completion.

## When to Use
Use this skill when you receive one or more tabular lab datasets (CSV/TSV/Parquet/DB extract) with inconsistent numeric formatting and possibly mixed units across sites, and you must produce a standardized dataset while avoiding ungrounded clinical assumptions or heuristic conversions.

## Procedure
- 1) Discover the contract and available documentation (checkpoint: conversion sources)
- Read the task instructions and note any explicit requirements: output path, required columns, unit system target, rounding/format rules, and missing-value policy.
- Inventory the working directory and nearby folders for metadata and tests (do not assume fixed filenames): list files and search for keywords like "unit", "ucum", "conversion", "mg/dL", "mmol/L", "umol/L".
- Open any provided feature description tables and extract unit strings and any stated conversion factors/formulas.
- If a verifier/test script is visible, extract any format/schema assertions and treat them as hard constraints.
- Decision: If no documented unit mapping exists for a column, mark it "undocumented" and plan to leave values unchanged (only parse/clean).
- 2) Validate and profile inputs before modification (checkpoint: schema snapshot)
- Load the dataset(s) and record: column names, dtypes, row count, and per-column missing/sentinel patterns (blank, "NA", "NaN", "-999", etc.).
- Identify candidate numeric columns using discovery (dtype + sample parsing), not a fixed list.
- Save a schema snapshot (columns and intended numeric columns) and a small profile per numeric column (min/median/max, quantiles) to compare after processing.
- Decision: Apply row filtering for missing values only if the task explicitly requires it; otherwise, preserve rows and represent missing as null consistently.
- 3) Parse numeric formats safely (checkpoint: parse success rates)
- Normalize numeric strings without changing meaning:
- Trim whitespace.
- Accept scientific notation via standard float parsing.
- Handle decimal commas only when unambiguous (for example, values match a decimal-comma pattern and do not also contain thousands separators); otherwise, leave unchanged and flag for review.
- Convert to numeric types (float) for intended numeric columns; keep a per-column count of parse failures and set failed parses to null.
- Decision: If parse failure rate is high for a column, stop and re-inspect raw patterns before proceeding to unit conversion.
- 4) Convert units using only documented rules, then validate by reloading output (checkpoint: post-write assertions)
- Build a conversion map strictly from discovered documentation (feature descriptions, unit columns, or visible standards referenced by the task). Each rule must include: source unit, target unit, factor/formula, and provenance (where it was found).
- Apply conversions only when:
- The column has an explicit unit label (or site-specific unit field) that matches a documented source unit, and
- The target unit is specified by the task or by the dataset standard you are asked to produce.
- Do not use range-based guessing, generic scaling (x10, x1000), tolerance clamping, or "try factors until in range" unless the task explicitly authorizes it.
- Write the output to the task-required location if specified; otherwise, write to a clearly named artifact in the current working directory.
- Execution anchor: Reload the written artifact and assert:
- Columns: required columns preserved; no unexpected drops/renames.
- Types: intended numeric columns parse as floats (or the required serialization type).
- Missingness: missing rate does not increase unexpectedly beyond parse failures; report before/after.
- Conversions: every converted column has a documented rule and a nonzero conversion count; columns without documentation must have zero conversions.

## Constraints / Pitfalls
- Never invent conversion factors, physiologic ranges, or unit identities. If documentation is missing or ambiguous, leave values unchanged and report the ambiguity (plus counts) rather than guessing.
- Do not apply clamping/tolerance or range-based "unit detection" as a default strategy; it can silently corrupt values and is only allowed when the task or visible verifier contract explicitly requires it.