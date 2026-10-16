# Lab Unit Harmonization

## Purpose
Harmonize multi-source clinical lab tables by cleaning numeric formats, detecting and converting units via range-based try-all-factors logic, and emitting a fixed-schema CSV with two-decimal plain-decimal values. The procedure derives per-feature ranges and conversion factors from a task-provided feature description file rather than from embedded literals.

## When to Use
Use when the task supplies a lab-value table plus a feature description file (ranges, units, conversion factors) and asks for a harmonized CSV with standardized units and numeric format. Do not use for free-text clinical notes or when no feature reference is provided.

## Procedure
- Discover inputs: list the working directory; locate the input lab CSV and the feature description file (columns typically include feature name, min, max, original unit, alternative units, conversion factors). Confirm the task-specified output path. Do not assume filenames.
- Load the feature description into two dicts: `ranges[feature] = (min, max)` and `factors[feature] = [list of multiplicative factors to original unit]`. If a feature in the data has no entry, skip conversion for it.
- Parse formats on every numeric cell: strip whitespace; if the string contains `e`/`E`, parse as scientific; else replace a single `,` with `.` to handle European decimals; cast to float; empty/NULL/`nan`/sentinel -> NaN.
- Drop rows containing any NaN across the numeric feature columns, then reset index.
- Range-based unit conversion per cell: if value is within `[min, max]`, keep exact value. Else iterate `factors[feature]`; return the first `value * factor` that lands within `[min, max]`. If none works, keep the original parsed value unchanged.
- Format every numeric cell as a string via `f"{x:.2f}"`. Write the CSV preserving the exact input column set and order.
- Post-write validation: reload the output CSV; assert column list equals input column list in order; assert every numeric cell matches regex `^-?\d+\.\d{2}$`; assert row count equals the filtered row count. Fix and rewrite if any assertion fails.

## Constraints / Pitfalls
- Never clamp, round-to-boundary, or widen ranges to force in-range: if no conversion factor yields an in-range value, keep the original parsed magnitude.
- No embedded ranges, conversion factors, or feature lists; always derive them from the discovered feature description file.
- Output must be plain decimal with exactly two decimals; no scientific notation, no thousand separators, no leading/trailing whitespace.
- Preserve the input column set and order exactly; do not add, drop, or rename columns.
- Do not fabricate a reference file path; if the feature description file cannot be located, stop and report rather than invent ranges.