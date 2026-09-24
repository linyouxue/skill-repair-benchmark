---
name: lab-unit-harmonization
description: Harmonize multi-source clinical lab data to US conventional units by
  (1) strict completeness filtering, (2) robust numeric parsing (scientific notation
  + comma decimals), (3) per-feature unit conversion using tight physiological ranges
  plus “best-candidate” selection (not by widening ranges), and (4) fixed `X.XX` formatting
  with correct validation (don’t confuse CSV delimiters with decimal commas).
---

## Steps
1. **Load inputs and identify numeric lab columns**
   1. Read `/root/environment/data/ckd_lab_data.csv` and `/root/environment/data/ckd_feature_descriptions.csv`.
   2. Treat all columns except the patient identifier column (if present) as lab features; keep the same column order for output.
   3. Inspect per-column missingness and rough distributions (min/max, quantiles) to spot likely mixed-unit analytes before converting.
2. **Parse raw numeric strings into floats (before dropping rows)**
   1. Normalize strings: strip whitespace; map `''`, `'nan'`, `'none'`, `'null'` to missing.
   2. Convert scientific notation via `float(s)` when it contains `e`/`E`.
   3. Fix comma/period issues with a **disambiguation rule**:
      - If a token contains **both** `,` and `.` (e.g., `1,234.5`), treat `,` as a thousands separator → remove commas.
      - Else if it contains `,` only (e.g., `12,34`), treat `,` as decimal separator → replace with `.`.
   4. Coerce failures to `NaN`.
3. **Drop incomplete records (strict)**
   1. After parsing, drop any row with **any** missing value in lab feature columns (`NaN`).
   2. Reset index.
4. **Unit harmonization with tight ranges + best-candidate selection (do not “fix” by widening ranges)**
   1. Define **US-conventional physiological ranges** per feature (min/max) and **candidate conversions** (multiplicative factors) for common SI/alt units (examples that must be covered because they commonly appear mixed in CKD lab exports):
      - Serum creatinine: µmol/L → mg/dL (× 0.0113)
      - BUN: mmol/L → mg/dL (× 2.801)
      - Hemoglobin: g/L → g/dL (× 0.1)
      - Calcium: mmol/L → mg/dL (× 4.0)
      - Phosphate: mmol/L → mg/dL (× 3.096)
      - Magnesium: mmol/L → mg/dL (× 2.43); **also** mg/L → mg/dL (× 0.1) to handle “7–9”-type magnitudes without expanding the acceptable mg/dL range
      - (Add other analytes as needed using the same pattern; keep ranges clinically tight rather than permissive.)
   2. For each column, compute a robust **target center** from already-in-range values (median of values within `[min,max]` after parsing). If none are in-range, use the midpoint `(min+max)/2`.
   3. For each value `v` in the column, evaluate candidates:
      - Candidate set includes “no conversion” (`v`) plus all `v*factor` conversions for that feature.
      - **Select the candidate that lands inside `[min,max]` and is closest to the column target center** (minimize `abs(candidate - center)`).
      - If **no** candidate falls inside range, set to `NaN` (do not silently keep out-of-range values).
   4. After converting all columns, drop any row that now has `NaN` (these are records that cannot be confidently harmonized to in-range US units).
5. **Round and format output as exact `X.XX` strings**
   1. Round numeric values to 2 decimals.
   2. Format every lab value with fixed 2-decimal string formatting: `f"{x:.2f}"` (no scientific notation).
   3. Save to `/root/ckd_lab_data_harmonized.csv` with `index=False`, preserving the **same columns and order** as input.
6. **Correct validation checks (avoid the CSV-comma mistake)**
   1. Do **not** assert “no commas anywhere in the file” (CSV delimiters are commas).
   2. Instead validate at the **cell level**:
      - No cell contains `','` (decimal comma) because values are formatted with `.`.
      - No cell contains `'e'`/`'E'` (scientific notation).
      - Every numeric cell matches regex `^-?\d+\.\d{2}$`.
      - Every numeric value lies within its configured physiological range.
## Expected Result
A CSV saved at `/root/ckd_lab_data_harmonized.csv` with the **same columns as the raw input**, only **complete patient rows**, all lab values converted to **US conventional units**, all values **within tight physiological ranges**, and every numeric value formatted exactly as `X.XX` (no scientific notation, no decimal commas, no inconsistent decimals).
