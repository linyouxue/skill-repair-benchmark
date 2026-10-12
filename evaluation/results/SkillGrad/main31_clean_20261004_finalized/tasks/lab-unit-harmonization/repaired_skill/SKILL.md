---
name: lab-unit-harmonization
description: Harmonize clinical lab tables by parsing numeric formats, converting units with an authoritative per-feature reference, and emitting standardized outputs while flagging ambiguous mixed-unit cases.
---

# Lab Unit Harmonization

## Overview

Lab Unit Harmonization provides techniques and references for standardizing clinical laboratory data from multiple sources. Real-world healthcare data often contains measurements in different units, varying decimal and numeric formats, and data entry inconsistencies that must be resolved before analysis.

This skill covers:
- **Unit Conversion**: Converting between US conventional and SI units
- **Format Standardization**: Handling scientific notation, decimal formats, whitespace
- **Data Quality Assessment**: Identifying and quantifying data issues
- **CKD-Specific Labs**: Complete reference for chronic kidney disease-related lab features

## When to Use This Skill

Use this skill when:
- Harmonizing lab values from multiple hospitals or health systems
- Converting between US conventional and SI units (e.g., mg/dL to µmol/L)
- Merging data from EHRs using different default unit conventions
- Integrating international datasets with mixed unit systems
- Standardizing inconsistent numeric formats (scientific notation, decimals)
- Cleaning whitespace, thousand separators, or European decimal formats
- Validating lab values against expected clinical ranges
- Preparing CKD lab panels for eGFR calculations or staging models
- Building ETL pipelines for clinical data warehouses
- Preprocessing lab data for machine learning models

## Data Quality Issues Reference

Real-world clinical lab data contains multiple types of quality issues. The following table summarizes common issues and their typical prevalence in multi-source datasets:

| Issue Type | Description | Typical Prevalence | Example |
|------------|-------------|-------------------|---------|
| **Incomplete Records** | Rows with excessive missing values | 1-5% | Patient record with only 3/62 labs measured |
| **Mixed Units** | Same analyte reported in different units | 20-40% | Creatinine: mg/dL vs µmol/L |
| **Scientific Notation** | Large/small values in exponential format | 15-30% | `1.5e3` instead of `1500` |
| **Thousand Separators** | Commas in large numbers | 10-25% | `1,234.5` vs `1234.5` |
| **European Decimals** | Comma as decimal separator | 10-20% | `12,5` vs `12.5` |
| **Whitespace Issues** | Leading/trailing spaces, tabs | 15-25% | `  45.2 ` vs `45.2` |
| **Missing Values** | Empty, NULL, or sentinel values | Variable | `NaN`, `-999`, blank |

### Features with Multiple Alternative Units

Some features have more than two possible unit representations:

**Three-Unit Features (8 total):**
| Feature | Unit 1 | Unit 2 | Unit 3 |
|---------|--------|--------|--------|
| Magnesium | mg/dL | mmol/L | mEq/L |
| Serum_Calcium | mg/dL | mmol/L | mEq/L |
| Hemoglobin | g/dL | g/L | mmol/L |
| Ferritin | ng/mL | µg/L | pmol/L |
| Prealbumin | mg/dL | mg/L | g/L |
| Urine_Creatinine | mg/dL | µmol/L | mmol/L |
| Troponin_I | ng/mL | µg/L | ng/L |
| Troponin_T | ng/mL | µg/L | ng/L |

## Core Workflow

The harmonization process follows these steps in order:

### Step 0: Filter Incomplete Records (Preprocessing)

Before harmonization, filter out rows with any missing values:

```python
def count_missing(row, numeric_cols):
    """Count missing/empty values in numeric columns"""
    count = 0
    for col in numeric_cols:
        val = row[col]
        if pd.isna(val) or str(val).strip() in ['', 'NaN', 'None', 'nan', 'none']:
            count += 1
    return count

# Keep only rows with NO missing values
missing_counts = df.apply(lambda row: count_missing(row, numeric_cols), axis=1)
complete_mask = missing_counts == 0
df = df[complete_mask].reset_index(drop=True)
```

**Rationale**: Clinical datasets often contain incomplete records (e.g., partial lab panels, cancelled orders, data entry errors). For harmonization tasks, only complete records with all features measured can be reliably processed. Rows with any missing values should be excluded to ensure consistent output quality.

### Step 1: Parse Numeric Formats

Parse all raw values to clean floats, handling:
- **Scientific notation**: `1.5e3` → `1500.0`
- **European decimals**: `12,34` → `12.34` (comma as decimal separator)
- **Whitespace**: "  45.2  " → `45.2`

```python
import pandas as pd
import numpy as np

def parse_value(value):
    """Parse a raw value to float; normalize exponent, commas, and whitespace."""
    if pd.isna(value):
        return np.nan

    s = str(value).strip()
    if s == '' or s.lower() == 'nan':
        return np.nan

    # Scientific notation
    if 'e' in s.lower():
        try:
            return float(s)
        except ValueError:
            pass

    # European decimals
    if ',' in s:
        s = s.replace(',', '.')

    try:
        return float(s)
    except ValueError:
        return np.nan

for col in numeric_cols:
    df[col] = df[col].apply(parse_value)
```

### Step 2: Unit Conversion (Range-Based Detection)

**Key Principle**: Use the per-feature reference (min/max + allowed conversions) as the *only* authority for when and how to convert.

Hard constraints:
- Load the provided per-feature reference table and mechanically derive `ref_ranges` and `ref_conversions` from it.
- **Hard stop (operational gate)**: before *any* conversion logic runs, you must (a) load/parse the reference via the reference-loading procedure and (b) pass `verify_reference(ref_ranges, ref_conversions, numeric_cols)` with **non-empty** `ref_ranges`; otherwise abort and fix reference loading/coverage.
- Do **not** create fallback dictionaries (e.g., `ranges`, `conversions`, `factors`, `physiologic_ranges`) unless they are direct outputs of the reference parser (prefer the canonical names `ref_ranges/ref_conversions`).
- If conversion is ambiguous (multiple candidates fit) or unresolved (none fit), keep the original value and emit an explicit status (and an audit artifact when required).

Algorithm (per cell):
1. If within the target-unit range → **keep as-is** (do not convert)
2. If out-of-range → try each candidate conversion listed for that feature
3. Accept the unique candidate that lands in-range (optionally with a small tolerance)
4. If multiple candidates land in-range or none do → **do not force**; leave unchanged and flag as ambiguous

```python
# Operational gate: make reference-derived inputs mandatory *before* defining conversion logic.
# (Parsing itself lives in references/reference-loading.md.)
ref_ranges, ref_conversions = load_reference_markdown(reference_path)
assert isinstance(ref_ranges, dict) and len(ref_ranges) > 0, "ref_ranges must be parsed from the authoritative reference"

ok, report = verify_reference(ref_ranges, ref_conversions, numeric_cols)
if not ok:
    raise ValueError(f"Reference not usable; refusing conversion: {report}")


def convert_range_triggered(value, feature, ref_ranges, ref_conversions, tol=0.0):
    """Range-triggered unit conversion using per-feature candidates only."""
    if pd.isna(value) or feature not in ref_ranges:
        return value, 'no_ref'

    lo, hi = ref_ranges[feature]

    def in_range(x):
        return (lo - tol) <= x <= (hi + tol)

    # Rule 1: already plausible in target unit -> keep
    if in_range(value):
        return value, 'kept_in_range'

    # Rule 2: only try conversions listed for this feature
    hits = []
    for factor in ref_conversions.get(feature, []):
        cand = value * factor
        if in_range(cand):
            hits.append(cand)

    if len(hits) == 1:
        return hits[0], 'converted'

    # Rule 3: ambiguity -> do not force
    return value, 'ambiguous_or_no_match'


for col in numeric_cols:
    df[col], df[col + '_status'] = zip(*df[col].apply(
        lambda v: convert_range_triggered(v, col, ref_ranges, ref_conversions, tol=0.0)
    ))
```

Decision rule: When the reference cannot be parsed/verified, stop and fix parsing/coverage; do not “make progress” by widening ranges, adding thresholds, or introducing guessed conversion factors.

Read references/reference-loading.md when the task provides a per-feature reference file (or path) and you must mechanically derive `ref_ranges`/`ref_conversions` and verify coverage before converting. Skip when the task already provides verified `ref_ranges` and `ref_conversions` as in-memory objects.

Read references/ambiguity-and-flagging.md when any cell yields `len(hits) != 1` (i.e., ambiguous multi-hit or no in-range candidate) and you need an audit artifact + a verification check that prescribes next actions. Skip when the dataset is guaranteed single-unit-per-feature and the reference candidates are non-overlapping.

### Step 3: Format Output (2 Decimal Places)

Format all values to exactly 2 decimal places (standard precision for clinical lab results):

```python
for col in numeric_cols:
    df[col] = df[col].apply(lambda x: f"{x:.2f}" if pd.notna(x) else '')
```

## Complete Feature Reference

See `reference/ckd_lab_features.md` for the complete dictionary of CKD-related lab features including min/max ranges, target units, and conversion candidates.

## Common Pitfalls

- **Reference-bypassing conversions**: If `ref_ranges/ref_conversions` were not parsed from the authoritative reference and verified for coverage, do not proceed; refusing to convert is better than plausible-looking heuristic conversions.
- **Blanket / heuristic conversions**: Unconditionally converting a feature (even if values are already in-range) silently pushes correct values onto the wrong scale; conversions must be range-triggered and reference-driven.
- **Overlapping plausible ranges**: When both unit interpretations look plausible, do not guess; keep the original value and flag the cell/feature for review.
- **Invented reference values**: Hard-coded “physiological ranges”, widened ranges, thresholds, or bespoke conversion factors bypass the authoritative reference table and produce plausible-looking but incorrect harmonization.
- **Clamping instead of diagnosing**: For out-of-range values, don’t clamp to min/max; try reference conversions, then leave unchanged + flag if unresolved.
- **Skipping parse before convert**: Failing to normalize scientific notation/decimal commas can create fake out-of-range values and trigger unnecessary conversions.

## Additional Resources

- `reference/ckd_lab_features.md`: Feature dictionary with ranges and conversion candidates
- [UCUM](https://ucum.org/): Unified Code for Units of Measure standard
