# Lab Unit Harmonization

## Purpose
Harmonize clinical lab values from heterogeneous sources into a single range-valid, fixed-precision numeric table. Given a lab dataset and a feature-description artifact, parse every numeric cell, normalize units into the canonical unit per feature, drop physiologically impossible rows, and emit the same shape with uniform decimal formatting.

## When to Use
Use when the input has mixed numeric formats (scientific notation, European decimals, whitespace) and/or mixed units across rows for the same analyte, and a feature artifact exists. Supports two branches: (A) artifact carries unit/range/alternative-unit metadata, or (B) artifact only names features and descriptions and the task permits clinical-knowledge grounding. Do not use when neither branch is available.

## Procedure
- Discover. List the working directory; identify the raw lab table, the feature description artifact, and the task-specified output path. Do not assume paths.
- Probe artifact schema. Print the artifact columns and 2 sample rows. Branch: (A) if columns include unit/range/factor fields, parse them to build the harmonization dict {feature: canonical_unit, (min,max), [factor_candidates]}; (B) if only Key/Name/Description exist, build the dict from clinical knowledge using wide pathology-inclusive ranges and inverse factors from alt_unit to canonical (e.g., umol/L to mg/dL for creatinine uses x/88.4, not x/0.0884). Log the chosen branch.
- Clean and parse. Drop rows with any empty/NaN/None/null/NA in dict columns. Parse each cell: strip whitespace; if comma present and no dot, treat comma as decimal; else strip commas as thousand separators; then float(). Mark unparseable rows for drop.
- Convert by range. For each cell and its (min,max): keep if in range; else try candidate factors in order and accept the first product in range; else mark the row for drop. Do not clamp except for sub-1% boundary drift.
- Calibrate. Compute per-feature drop counts. If total drop rate > 5%, print the top out-of-range raw samples per offending feature, widen that feature's range or add an inverse factor (verify factor direction against a known reference value), and re-run step 4. Stop when drop rate stabilizes or hits a documented floor.
- Format and write. Apply f"{x:.2f}" to every numeric cell, preserve input column order and non-numeric columns, and write to the task-specified output path. If the write fails, diagnose permissions/mounts; do not silently redirect.
- Verify. Reload the output. Assert: columns and row count match post-filter state; every numeric cell matches ^-?\d+\.\d{2}$; every value lies within its (min,max). Print both violation counts; both must be zero.

## Constraints / Pitfalls
- Do not hardcode a feature table inside this skill; build it per run from the artifact (branch A) or from clinical knowledge invoked at runtime (branch B). Sibling tasks have different features.
- Verify unit-conversion factor direction with one known reference value per feature before applying it to the column; a common error is inverting the factor (e.g., 1/0.0884 vs 1/88.4).
- Treat comma as decimal only when no dot is present in the token.
- Parse before range-checking; otherwise strings like "1,5e3" misfire.
- The post-write reload-and-assert step is mandatory; in-memory success is not sufficient.
- If branch B is used, prefer wider pathology-inclusive ranges over textbook healthy-adult ranges to avoid dropping legitimate diseased-cohort values.