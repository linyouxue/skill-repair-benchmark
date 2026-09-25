# SKILL.md

## When to use
Use this skill when you must **harmonize heterogeneous clinical lab CSV data** coming from multiple sources with:
- **Mixed units** for the same analyte (some rows/values in alternative units).
- **Inconsistent numeric formatting**, including:
  - scientific notation (e.g., `1.23e2`)
  - decimal commas (e.g., `12,34`)
  - varying decimal precision
- **Incomplete rows** that must be removed rather than imputed.

Before acting, gather evidence from:
- The **raw lab table** (shape, column names, dtypes, missingness patterns, example values per column).
- The **feature description file** to interpret abbreviations and decide which analytes plausibly have unit mismatches.
- A **target unit convention** (e.g., “US conventional units”) and **reasonable physiological ranges** per analyte to flag likely mis-unit values.

## Possible Failure Modes
- **Dropping the wrong rows**: removing rows with any non-critical missingness vs. the task’s requirement (often “drop rows with any missing values” in the provided lab columns).  
- **Partial parsing of numeric strings**:
  - leaving commas untouched (`"1,2"` becomes `12` or fails parsing),
  - leaving scientific notation in output,
  - accidentally treating thousands separators as decimal commas (or vice versa).
- **Mixing per-column and per-cell logic incorrectly**:
  - applying a unit conversion to the entire column when only some values are in the alternate unit,
  - converting values that are already in the correct unit (double conversion).
- **Using implausible or inconsistent physiological ranges** leading to:
  - converting true outliers that are clinically possible,
  - missing true unit-mismatch values.
- **Rounding/formatting errors**:
  - rounding before conversion (accumulating errors),
  - outputting floats without fixed 2-decimal formatting (`X.X` or `X` instead of `X.XX`),
  - generating scientific notation after rounding/CSV write.
- **Changing the dataset schema**:
  - altering column count/order,
  - accidentally converting identifier columns or non-lab categorical columns (if present).
- **Silent coercion to NaN** during parsing, then dropping many rows unexpectedly without diagnosing why.

## Possible procedures
1. **Load & profile**
   - Read the lab CSV with pandas, keeping raw strings initially (avoid premature dtype inference).
   - Read the feature description file to map short names → analyte meaning.
   - Compute for each column:
     - % missing, sample raw unique patterns (e.g., strings containing `,` or `e`/`E`),
     - numeric parse success rate after cleaning.

2. **Row removal policy**
   - Decide the exact dropping rule consistent with the contract (commonly: drop any row with missing across lab features).
   - Apply dropping *after* ensuring that “missing” includes empty strings and non-parsable entries you can’t recover.

3. **Normalize numeric text to parseable form**
   - For each lab feature column intended to be numeric:
     - Strip whitespace.
     - Convert decimal comma to dot **only when it is a decimal comma** (typical heuristic: if string contains `,` and not `.` then replace `,`→`.`; be cautious if both appear).
     - Preserve negative signs if medically plausible for that analyte (many are non-negative; still parse safely).
     - Parse scientific notation with `pd.to_numeric(..., errors="coerce")`.
   - Track columns/rows where parsing produced NaN to diagnose formatting issues vs. true missingness.

4. **Unit harmonization via range-based detection**
   - For each analyte that commonly has cross-system unit differences:
     - Define an expected **physiological range** in the target unit (broad enough to include plausible values).
     - Define one or more **alternate-unit transforms** (multiplicative factor, possibly additive for temperature-like measures; most labs are multiplicative).
   - Apply **per-cell conditional conversion**:
     - If value falls far outside the target-unit range but falls inside the plausible range *after* applying a candidate conversion, convert it.
     - If multiple conversions “fit,” choose deterministically (e.g., smallest absolute deviation from typical median, or prioritize the most common cross-unit mapping for that analyte).
   - Keep a conversion audit (counts converted per column) to sanity-check that conversions are not over-applied.

5. **Post-harmonization validation & cleanup**
   - Re-check each column:
     - min/max/quantiles vs expected range,
     - remaining out-of-range values (flag for review; don’t blindly clip unless contract allows).
   - Ensure no scientific notation remains:
     - format values explicitly rather than relying on default float rendering.

6. **Formatting and saving**
   - Round to 2 decimals **after** all conversions.
   - Enforce fixed `X.XX` formatting (e.g., format as strings with `"{:.2f}"`) to guarantee evaluator-visible formatting constraints.
   - Save to the required path with:
     - same columns (count and order) as input,
     - no index column unless the input had one intentionally.

7. **Recovery checks**
   - If too many rows are dropped:
     - inspect whether parsing/decimal replacement created NaNs,
     - adjust parsing heuristics.
   - If many values in a column are still out of range:
     - re-evaluate which unit conversion(s) are appropriate for that analyte,
     - ensure you didn’t confuse target vs alternate unit direction.

## Verification Checklist
- [ ] Output file written to the required location and readable as a CSV.
- [ ] **Same number of columns** as input, with the same column order and names.
- [ ] All remaining rows have **no missing values** (per the contract’s dropping rule).
- [ ] No cell contains:
  - scientific notation (`e`/`E`),
  - decimal commas,
  - variable decimal lengths (every numeric is `X.XX`).
- [ ] All lab columns are in the **target unit system** and values fall within defined **physiological ranges** (check min/max and a few random samples).
- [ ] Unit conversions were applied **selectively** (audit counts per column; ensure not 0 when expected, not ~100% unless justified).
- [ ] Non-lab/identifier columns (if any exist) were not unintentionally transformed.
- [ ] If validation fails (unexpected drops, out-of-range spikes), rerun diagnostics on parsing and conversion heuristics rather than forcing values to fit.
