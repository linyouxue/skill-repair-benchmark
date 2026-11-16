# Lab Unit Harmonization

## Purpose
Harmonize clinical laboratory values from heterogeneous sources into a single, range-valid, consistently formatted numeric table. The task family: given a tabular lab dataset plus a feature-description artifact that defines each feature's expected range and alternative units, produce an output with the same shape where every numeric cell is parsed, unit-normalized into the canonical unit, and formatted to a fixed decimal precision.

## When to Use
Use when the input contains mixed numeric formats (scientific notation, European decimals, whitespace), mixed units across rows for the same analyte, and a companion metadata file (for example a feature description CSV) that lists each feature with its canonical unit, expected min/max, and alternative units or conversion factors. Do not use when no authoritative range/unit metadata is discoverable in the environment.

## Procedure
- Discover inputs. List the working directory. Identify (a) the raw lab table, (b) the feature description artifact (search for names containing "feature", "description", "ckd", or ".csv" metadata), and (c) the task-specified output path. If any of the three is not explicitly supplied by the task, stop and ask or inspect task files rather than assuming a path or inventing a reference file.
- Build the harmonization dictionary from the feature description artifact at runtime. Parse it to produce, per feature: canonical_unit, (min, max), and an ordered list of candidate multiplicative factors derived from the alternative units listed for that feature. Do not hardcode feature lists, ranges, or factors inside the skill; the artifact is the source of truth. Print the number of features parsed and spot-check two entries.
- Filter rows with any missing or sentinel value (empty string, "NaN", "None", "nan", "null", or NA) across the numeric columns defined by the harmonization dictionary. Keep only fully populated rows and reset the index.
- Parse every numeric cell to float with a single helper that: (1) strips whitespace, (2) returns NaN for empty/na tokens, (3) accepts scientific notation via float(), (4) if a comma is present and no dot is present, treats comma as the decimal separator (replace "," with "."), (5) otherwise strips thousand-separator commas. Reject values that still fail to parse by marking the row for drop.
- Convert units by range. For each cell and its feature's (min, max): if min <= value <= max keep as is; else iterate the ordered candidate factors and return the first product that lands inside (min, max). If no factor lands the value in range, drop the row (do not clamp, do not keep an out-of-range value). Clamping is only permitted for sub-1% floating point drift exactly on the boundary.
- Format every numeric cell with f"{x:.2f}" so each cell matches the regex ^-?\d+\.\d{2}$.
- Write to the task-specified output path only. Do not silently redirect to a different path if the write fails; diagnose permissions or mount issues first.
- Verify. Reload the written file. Assert (a) column set equals the harmonized column set, (b) row count equals the filtered row count, (c) every numeric cell matches ^-?\d+\.\d{2}$, (d) for every feature every value lies within its (min, max). Print the counts of format violations and range violations; both must be zero before declaring completion.

## Constraints / Pitfalls
- Do not hardcode feature names, ranges, or conversion factors in this skill. Derive them from the task-provided feature description artifact every run; sibling tasks will have different features and ranges.
- Do not invent or reference internal "reference/*.md" files that are not present in the environment. Only use artifacts discovered in the task directory.
- Do not clamp arbitrary out-of-range values to the boundary. If no candidate factor brings a value into range, drop the row; the verifier expects all retained values to be physiologically valid.
- Parse formats before attempting unit conversion; otherwise range checks will misfire on strings like "1,5e3" or " 12,34 ".
- Treat comma as a decimal separator only when no dot is present in the token; otherwise treat comma as a thousand separator.
- The output must preserve input column order and non-numeric columns unchanged; only numeric columns in the harmonization dictionary are transformed.
- The post-write verification step is mandatory. Do not claim completion based on in-memory state alone; reload the written artifact and assert the format regex and range membership.