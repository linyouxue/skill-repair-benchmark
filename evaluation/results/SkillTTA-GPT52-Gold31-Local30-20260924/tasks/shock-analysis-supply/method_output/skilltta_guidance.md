# SKILL.md

## When to use
Use this skill when the task requires building an **Excel-only** macro/production-function model that combines:
- **Online data collection** from multiple official sources (e.g., productivity dataset, IMF forecasts, central bank/statistical portal series),
- **Populating a provided Excel template** (specific sheets/columns/rows),
- **Formula-driven calculations only** (no Python, no manual “calculator” values in computed cells),
- **Trend-cycle extraction (HP filter)** implemented inside Excel (often via **Solver**),
- And a **counterfactual capital/investment shock** propagated through a Cobb–Douglas framework to produce potential output paths.

Before acting, gather evidence from:
- The workbook structure (sheet names, required columns/rows, which cells are inputs vs computed),
- Source metadata/definitions (to ensure correct variable choice, units, and timing),
- The time coverage demanded (historical + projections + extension rules),
- Any “latest available year” constraints for specific series (e.g., capital stock ending earlier than GDP),
- Whether the template expects levels vs logs, real vs nominal, local currency vs USD, per-capita vs aggregate.

## Possible Failure Modes
- **Hardcoding computed cells**: typing numbers into cells that should be formulas (especially projections, depreciation rates, ln transforms, K extensions, production function outputs).
- **Wrong variable/units from sources**: selecting a similarly named series (nominal vs real, index vs level, per-capita vs total) or mixing base years/units across sources.
- **Misaligned years**: shifting series by one row/year, mixing fiscal/calendar years, or pasting data not matching the template’s year labels.
- **Breaking links between sheets**: copying values instead of referencing source sheets, or overwriting formulas with pasted values.
- **Projection logic errors**: extending growth rates incorrectly (e.g., applying growth additively to levels instead of multiplicatively, or forgetting to hold the terminal growth constant through the horizon).
- **Depreciation rate mistakes**: using the wrong sign or timing for depreciation, mismatching capital stock and consumption-of-fixed-capital series, or averaging the wrong window (e.g., not the “most recent N years” requested).
- **HP filter mis-specification**:
  - Objective function not reflecting the standard HP criterion (fit + smoothness penalty),
  - Second-difference term computed incorrectly,
  - Solver changing the wrong decision range,
  - Constraints missing (or unnecessary constraints added) leading to non-smooth/unstable trend.
- **Capital extension errors**: extending K using an “anchor” incorrectly (wrong averaging window, applying K/Y ratio to wrong Y series, or using non-matching years).
- **Shock implementation errors**: misplacing the shock timing, mixing currency units, or failing to translate investment spending into ΔK consistently with depreciation/accumulation logic.
- **Template integrity issues**: editing outside requested areas, renaming sheets, changing formats that downstream formulas rely on.

## Possible procedures
### 1) Triage the workbook contract (before collecting data)
- Open the Excel template and identify:
  - Input areas vs calculated blocks,
  - The exact year rows used in each sheet,
  - Any pre-existing formulas you must preserve,
  - Where cross-sheet links are expected (look for blank cells in computed tables and for named headers).
- Decide a “no-overwrite rule”: when pasting, paste **values only** into designated raw-data input columns, and do not paste over formula ranges.

### 2) Collect and map data with metadata checks
- For each source dataset:
  - Use the dataset’s metadata/variable definitions to confirm you are pulling the intended concept (e.g., real output level, capital stock measure, depreciation-related series).
  - Confirm units (millions/billions, constant prices/base year, national currency vs USD) and ensure consistency with the template’s expectations.
- Record provenance in a lightweight way:
  - Keep URLs and series names/identifiers in adjacent notes or a designated “source” column if available (without altering required structure).

### 3) Populate raw data tabs (keep calculations in Excel)
- Paste raw series into the specified columns/rows only.
- For any required derived columns (growth, projections, ratios, logs), use formulas that reference the pasted raw data.
- For projections based on growth rates:
  - Implement compounding with formula logic (e.g., next level = prior level × (1 + growth)).
  - If instructed to hold a terminal growth rate constant, reference that terminal growth cell for all subsequent years (avoid retyping the rate).

### 4) Compute depreciation rate from capital and CFC
- Link capital stock values from the designated sheet (do not duplicate numbers).
- Compute annual depreciation rate using consistent timing (confirm whether the template expects CFC/K(t) or CFC/K(t−1)).
- Compute the requested average over the specified most-recent window using formulas (e.g., `AVERAGE` over a dynamically identified range or a fixed last-N-year block that matches the sheet’s final populated years).
- Feed that average depreciation into the production/accumulation logic via a single referenced cell.

### 5) Set up HP filter block in Excel with Solver
- Create/confirm:
  - A column for the observed series in logs (e.g., ln output, ln capital, ln productivity residual if applicable),
  - A trend placeholder range (decision variables),
  - A second-difference column computed from the trend placeholder (ensure correct indexing),
  - An objective cell that sums:
    - squared deviations (observed − trend),
    - plus smoothing penalty × squared second differences.
- Solver setup (typical pattern):
  - **Set Objective**: the objective cell to **Min**,
  - **By Changing Variable Cells**: the trend placeholder range,
  - Use a stable solving method (often GRG Nonlinear works; if unstable, try evolutionary only as last resort).
- Sanity checks after Solver:
  - Trend should be smooth (second differences not erratic),
  - Residual/cycle should not be identically zero unless forced,
  - Any “check” column intended to be zero at initialization should behave as the template expects before solving.

### 6) Production function and scenario build-out
- Build the baseline potential output using linked trend productivity and Cobb–Douglas structure:
  - Ensure α (capital share) is referenced from the template’s parameter cell(s),
  - Use log/level consistency (if working in logs, exponentiate back only where required).
- Extend capital stock beyond the last observed year using the instructed anchoring method:
  - Compute the anchor statistic (e.g., average ratio over specified recent years) in a dedicated cell,
  - Apply it consistently to the projected output series to derive extended capital.
- Implement the investment shock:
  - Map shock years and amount schedule in the specified “Investment” sheet/range,
  - Translate spending into ΔK and updated capital path using accumulation formulas and the depreciation assumption,
  - Compute “with-shock” potential output from the new capital path.

### 7) Recovery checks during build
- If numbers look implausible (exploding capital, negative GDP, discontinuities):
  - Re-check units and scaling (billions vs millions),
  - Confirm growth rates are decimals vs percentages,
  - Confirm year alignment between series,
  - Confirm Solver changed the intended cells and did converge.

## Verification Checklist
- **Excel-only compliance**
  - No external scripts used to compute model outputs; all computations are Excel formulas.
  - No hardcoded constants in cells that are meant to be calculated (projections, averages, ratios, logs, ΔK/K paths, production function outputs).
- **Template adherence**
  - Correct sheets populated (raw data tabs filled only in designated input columns/rows).
  - Cross-sheet links exist where expected (cells reference other sheets rather than duplicated values).
  - No accidental overwriting of pre-existing formulas or table structures.
- **Data correctness**
  - Series match the intended definitions (checked against metadata).
  - Units are consistent across sheets (and growth rates treated as decimals vs percentages correctly).
  - Years align across datasets and the template’s year labels.
- **Projection logic**
  - Terminal growth rate extension is applied exactly as instructed (held constant through horizon).
  - Level projections compound correctly year-to-year.
- **Depreciation**
  - Depreciation rate formula references the correct CFC and capital stock columns.
  - The “most recent N years” average uses the correct window and updates if underlying data changes.
- **HP filter**
  - Objective cell references the full intended ranges.
  - Solver decision range is correct; objective decreases after solving.
  - Trend series is smooth and consistent; diagnostic columns behave as intended.
- **Scenario outputs**
  - Baseline and with-shock capital paths are internally consistent with depreciation and investment.
  - Potential output paths (baseline vs shock) differ only due to modeled channels (not due to broken links or pasted values).
- **Non-copying from retrieved examples**
  - No imported code patterns, constants, or irrelevant structures from unrelated examples; only general workflow discipline is applied.
- **Final deliverable**
  - Saved workbook is `test-supply.xlsx` with all formulas preserved and recalculating without errors (check for `#REF!`, `#VALUE!`, circular references unless explicitly intended and stable).
