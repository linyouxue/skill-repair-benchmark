---
name: skilltta-task-guidance
description: Task-specific operational guidance synthesized at test time from retrieved training examples.
---

# SKILL.md

## When to use
Use this skill when the target task requires building a supply-side macroeconomic shock analysis for a small open economy inside a provided Excel workbook, using a Cobb-Douglas production function decomposition (Y = Z · K^α · L^(1-α) or logged equivalent), an HP filter for TFP trend, and projections extended by an investment shock. The contract is Excel-only: every derived cell must be a live formula referencing source cells; no hardcoded numeric results, no Python computation, and no altering of the workbook's sheet/column layout.

Before acting, the future agent should gather:
- The workbook's exact sheet names, header rows, and which cells are inputs vs. computed placeholders.
- Source data definitions (PWT metadata for capital stock, labor share, employment; IMF WEO real GDP level and growth; ECB consumption of fixed capital; investment schedule sheet).
- Time coverage required by each sheet (historical window vs. projection horizon) and the anchor/averaging windows specified in the prompt (e.g., "most recent N years").
- The exact target output filename and that it must open cleanly in Excel with formulas intact.

## Possible Failure Modes
- Pasting numeric values into cells that the prompt says must be calculated (breaks the "no hardcoded numbers" rule).
- Using Python/pandas to compute results and then writing values into Excel instead of writing formulas.
- Misreading PWT variable codes (e.g., confusing rnna/rkna capital stock variants, cgdpo vs rgdpo, emp vs. pop, labsh vs. 1-labsh) — always consult the PWT metadata sheet first.
- Pulling nominal instead of real GDP from IMF WEO, or mixing units (billions vs. millions, USD vs. local currency, index vs. level).
- Extending the WEO growth rate incorrectly: the level for year t must be level_{t-1} · (1 + g_t/100), applied recursively via formula, not by copying a constant level.
- Depreciation rate defined inconsistently with the capital law of motion (δ_t should match CFC_t / K_{t-1} or CFC_t / K_t as the model requires; be consistent across the workbook).
- HP filter setup errors: wrong second-difference formula (should be (x_{t+1} − x_t) − (x_t − x_{t-1})), wrong λ (annual data conventionally uses 6.25 or 100 — check any hint in the sheet), objective not summing squared deviations plus λ · sum of squared second differences, or Solver changing the wrong cell range.
- Forgetting that endpoints of the HP-smoothed series have no second-difference constraint; the changing-cell range must still cover them.
- Extending capital stock K past the last PWT year without anchoring K/Y to the specified recent-years average, or anchoring to the wrong window length.
- Using TREND() with the wrong known_y / known_x ranges so LnZ trend extrapolation drifts.
- Building Ystar with the wrong capital share (α vs. 1−α confusion between labsh and capital share).
- Not linking the investment shock sheet's ΔI into ΔK and then into K_with via the perpetual inventory identity K_t = (1−δ)·K_{t−1} + I_t.
- Overwriting or renaming sheets/columns the grader inspects; saving under a different filename than requested.
- Losing formulas by copy-pasting values, or by using tools that flatten formulas on save.

## Possible procedures
1. Inspect the workbook first. Open each sheet, note existing headers, placeholder columns, and any comments/hints. Do not restructure.
2. Data collection phase:
   - PWT: identify the correct series from the metadata sheet (real GDP, capital stock, labor share, employment) for the target country. Link cells with formulas referencing a raw-data staging area or direct entries only in the designated input cells.
   - IMF WEO via Playwright MCP: fetch real GDP level and real GDP growth for the specified span. Enter historicals as inputs; compute projected levels by formula GDP_t = GDP_{t-1}*(1+g_t/100). For years past the last published growth, reference the last-year growth cell so the extension is formula-driven.
   - ECB CFC: enter annual CFC values as inputs. Link K from PWT and compute δ_t by formula in each row.
   - Average recent-N-year depreciation via AVERAGE() over the exact trailing window specified.
3. Production sheet linking:
   - Use = 'SheetName'!cell references to pull K and Y into the LnK/LnY columns; compute logs with LN().
   - Compute LnZ = LnY − α·LnK − (1−α)·LnL (or the exact decomposition implied by the workbook's columns and the chosen capital share).
4. HP filter with Solver:
   - Column layout suggested by the prompt: F = LnZ, L = LnZ_HP (changing cells, seeded equal to F), N = second-order differences of L, and a column for (LnZ − LnZ_HP).
   - Objective P5 = SUMSQ(deviations) + λ · SUMSQ(second differences). Verify λ.
   - Run Solver: minimize P5 by changing L6:L27 (or the full HP column range), no constraints, GRG Nonlinear.
   - Sanity: with L=F initially, deviations sum to 0 and objective equals λ·SUMSQ(second diffs).
5. Projection:
   - K/Y anchor: compute AVERAGE of the last 9 K/Y ratios (or the count the prompt states), then extend K_t = anchor · Y_t for future years, or apply the perpetual-inventory recursion if the sheet's structure demands it.
   - LnZ trend extension: use =TREND(known_LnZ_HP, known_years, future_years) to fill forward.
   - Ystar_base = EXP(LnZ_trend) · K^α · L^(1-α), all via formula.
   - Investment shock: link the annual investment amounts from the Investment sheet, compute I_with_t = I_base_t + shock_t across the 8-year window, then K_with_t = (1−δ)·K_with_{t−1} + I_with_t.
   - Ystar_with computed with K_with and the same LnZ_trend and labor path.
   - Fill remaining columns (differences, % gaps) with formulas referencing the two Ystar series.
6. Save as the exact filename requested, verify by reopening that formulas persist.

Decision points / recovery:
- If Solver fails to converge, reseed L column to F, re-check second-difference formula and objective, and rerun.
- If Ystar_base does not match Y closely in-sample, re-check α vs. 1−α assignment and log base consistency.
- If projected GDP jumps at the seam year, verify the growth-rate carry-forward formula and that no year is skipped.

## Verification Checklist
- [ ] Every computed cell contains a formula referencing inputs or other cells; no bare numeric results in derived cells.
- [ ] No Python or external computation was used to produce values pasted into the workbook.
- [ ] Sheet names, tab order, and column layouts are unchanged from the provided template.
- [ ] PWT variables chosen match the metadata definitions for capital stock, output, labor share, and employment.
- [ ] IMF WEO series is real GDP (level and growth); projected levels are recursively computed via formula and the post-last-forecast years reference the terminal growth rate cell.
- [ ] ECB CFC values entered as inputs; depreciation rate computed by formula each year; the "recent 8 years average" cell uses AVERAGE over exactly the specified window.
- [ ] HP filter: LnZ_HP is the Solver changing range, second differences are correct, objective combines squared deviations and λ·squared second differences, Solver converged to a smooth series.
- [ ] K/Y anchor uses the exact averaging window specified and K extension uses formulas.
- [ ] LnZ trend extension uses TREND() on the HP-filtered series with correct known/future ranges.
- [ ] Capital's share vs. labor's share is applied consistently in both Ystar_base and Ystar_with.
- [ ] Investment shock enters K_with via the perpetual-inventory identity and only during the specified 8-year window.
- [ ] Output workbook saved with the required filename; reopening confirms formulas are live.
- [ ] No content, values, or names copied from retrieved examples (those examples are code-generation tasks unrelated to this Excel workflow and must not influence numeric choices).
- [ ] Unrelated sheets/cells outside the task's scope are untouched.
- [ ] Recovery: if any data source is ambiguous, document the assumption in a cell comment rather than hardcoding a value.
