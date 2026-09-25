# SKILL.md

## When to use
Use this skill when you must produce a **day-ahead unit commitment (UC) schedule** from a provided power-system JSON test case, and write a **structured JSON report** that an independent verifier will re-check for feasibility and accounting consistency.

Before acting, gather evidence from the input case file (e.g., the referenced `network.json`) for:
- The **time horizon length** (e.g., 24/48 hours) and indexing conventions.
- **System demand** per hour and **spinning reserve requirement** per hour (treated as *system-wide totals*).
- Generator lists split into **thermal** vs **renewable**, with each unit’s:
  - Operating limits (min/max output and availability over time, if any)
  - Ramping limits
  - Minimum up/down times
  - Startup/shutdown characteristics and costs (if present)
  - Initial conditions (on/off state, time-in-state, initial output, etc.)
  - Must-run flags or fixed commitments (if present)
  - Cost model needed to compute objective cost
- Any special modeling notes in the prompt (e.g., “don’t model contingencies/branch flows”, “don’t rescale data”, “reserve from online thermal headroom”, “thermal production is total MW, not above minimum”).

## Possible Failure Modes
- **Editing or normalizing input data** (rescaling, removing records, or “fixing” values) instead of treating it as immutable.
- **Reserve modeling mistakes**:
  - Counting reserve from offline units, renewables, or non-thermal resources when it must come from **online thermal**.
  - Treating reserve as “extra above max” or ignoring headroom: reserve should be limited by *(Pmax − scheduled production)* (and any reserve capability constraints, if present).
- **Incorrect production semantics**: reporting thermal output as “above minimum” instead of **total MW produced**.
- **Demand balance errors**:
  - Not meeting system demand each hour (including mis-handling curtailment/renewables).
  - Confusing nodal vs system demand when the task requires **total hourly system demand** only.
- **Minimum up/down logic bugs**:
  - Startup/shutdown arrays inconsistent with commitment changes.
  - Not enforcing time-in-state from initial conditions.
- **Ramping violations**: forgetting ramp constraints across hours, especially across hour 1 using initial output.
- **Generator limit violations**:
  - Commitment = 0 but production > 0.
  - Production below Pmin when committed, or above Pmax.
  - Renewables exceeding their hourly availability/capacity.
- **Report-format mismatches**:
  - Wrong generator names (must match input exactly).
  - Wrong time indexing (hourly summary starts at **1**).
  - Wrong vector lengths per time period.
  - Filling constraint checks with “pass” despite an infeasible schedule (verifier will recompute and fail).
- **Inconsistent objective reporting**: reporting an objective cost that doesn’t match the schedule under the case’s cost definitions.
- **Solver status/gap mishandling**: claiming “optimal” without evidence; reporting a gap incorrectly or not using `null` when unknown.

## Possible procedures
1. **Parse and validate the case (without modifying it)**
   - Load JSON and identify fields for time periods, demand series, reserve series, and generator attributes.
   - Partition units into thermal vs renewable according to case metadata (not by guessing from names).
   - Validate basic shapes: every hourly series length equals the horizon length; generator parameter arrays (if any) align to hours.
   - If the case is ambiguous, extract and log assumptions *internally* and prefer conservative feasibility (e.g., treat missing ramp as unconstrained only if the format indicates so).

2. **Formulate a UC optimization model (MILP is typical)**
   - Indices: generator `g`, hour `t`.
   - Decision variables (thermal):
     - `u[g,t]` ∈ {0,1} commitment
     - `p[g,t]` ≥ 0 production (total MW)
     - `r[g,t]` ≥ 0 spinning reserve scheduled
     - `su[g,t]`, `sd[g,t]` ∈ {0,1} startup/shutdown indicators (or derive consistently)
   - Decision variables (renewables):
     - `pr[gr,t]` ≥ 0 renewable production (bounded by availability)
   - Core constraints:
     - **Demand balance** per hour: sum thermal `p` + sum renewable `pr` = demand (unless the case explicitly allows load shedding; if not stated, do not introduce it).
     - **Thermal limits**: if committed, enforce Pmin ≤ p ≤ Pmax; if not, p = 0.
     - **Renewable limits**: 0 ≤ pr ≤ available (hourly) or capacity.
     - **Reserve requirement**: sum thermal `r[g,t]` ≥ reserve_requirement[t].
     - **Reserve feasibility/headroom**: r[g,t] ≤ (Pmax[g,t] − p[g,t]) and r[g,t] = 0 if u[g,t] = 0.
     - **Startup/shutdown logic**: u[g,t] − u[g,t−1] = su[g,t] − sd[g,t] (handle `t=1` with initial status).
     - **Minimum up/down time**: enforce using standard MILP formulations; incorporate initial time-in-state.
     - **Ramping**: |p[g,t] − p[g,t−1]| bounded by ramp limits (with separate up/down if provided), conditioned on on/off transitions if required by case definitions.
     - **Must-run/fixed commitment**: enforce if present.
   - Objective:
     - Minimize total cost consistent with case data: energy production costs (piecewise/linear/quadratic as specified), no-load costs, startup/shutdown costs, etc.
     - Avoid inventing penalty terms unless the case format explicitly defines them.

3. **Solve robustly**
   - Prefer a MILP solver available in the environment (e.g., CBC/HiGHS/Gurobi) and set reasonable time limits if needed.
   - Capture:
     - solver termination status → map to one of: `optimal`, `feasible`, `time_limit_feasible`, `suboptimal_feasible`, `heuristic_feasible`
     - MIP gap if solver provides it; otherwise store `null`.
   - If optimal solve fails:
     - Attempt a fallback: relax integrality to get a bound, warm-start, or run a heuristic commitment (e.g., commit cheapest feasible set respecting min up/down) then re-optimize.
     - Always prioritize **feasibility** over cost if forced to choose.

4. **Construct the report JSON exactly as required**
   - Use **exact generator names** from input.
   - Ensure arrays `commitment`, `production_MW`, `reserve_MW`, `startup`, `shutdown` have length = `time_periods`.
   - Thermal production should be the **total MW** output for that unit and hour.
   - `hourly_summary`:
     - `hour` starts at 1 and increments by 1
     - include totals: demand, thermal generation total, renewable generation total, reserve requirement, scheduled spinning reserve total.
   - `summary` fields:
     - Populate counts, horizon length, objective cost, solver status, gap, and totals for startups/shutdowns.
     - Compute max violations/shortfalls from your own post-checks (should be 0.0 for a valid final submission).

5. **Run internal post-solve constraint checks (mirror the verifier)**
   - Recompute every required check from the produced schedule (not from model feasibility flags):
     - demand balance per hour (track max absolute deviation)
     - reserve requirement and reserve deliverability (headroom)
     - generator limits, ramping, min up/down, must-run, initial conditions, renewable bounds
     - startup/shutdown consistency with commitment transitions
     - cost consistency by re-evaluating the objective from schedule outputs
   - If any check fails:
     - Identify the smallest set of violated constraints (by hour/unit).
     - Fix systematically (e.g., adjust reserve allocation before changing commitment; enforce p=0 when u=0; repair min up/down with commitment edits), then re-solve/re-check.

## Verification Checklist
- [ ] Input case was only **read**, not modified, removed, or rescaled.
- [ ] Report JSON matches the required schema; all required keys exist and types are correct.
- [ ] Generator `name` fields **exactly** match input identifiers (no renaming, trimming, or re-order-dependent assumptions).
- [ ] `time_periods` equals the case horizon; all per-hour arrays have exactly that length.
- [ ] `hourly_summary.hour` starts at **1** and aligns with the first time period used in schedules.
- [ ] For every thermal unit/hour: if commitment = 0 then production_MW = 0 and reserve_MW = 0.
- [ ] For every committed thermal unit/hour: Pmin ≤ production_MW ≤ Pmax, and reserve_MW ≤ (Pmax − production_MW).
- [ ] Hourly demand balance holds (max deviation = 0.0 within strict tolerance expected by the benchmark).
- [ ] Hourly spinning reserve requirement is met using **online thermal** reserve only; max reserve shortfall = 0.0.
- [ ] Ramping constraints hold across all hour-to-hour transitions, including hour 1 vs initial conditions.
- [ ] Minimum up/down constraints and startup/shutdown logic are consistent with initial conditions and transitions.
- [ ] Renewable production respects hourly availability/capacity limits.
- [ ] `objective_cost` equals a recomputation from the final schedule using the case’s cost definitions.
- [ ] `solver_status` and `reported_mip_gap` are truthful: gap is nonnegative or `null` if not derivable.
- [ ] `constraint_check` fields are all `"pass"` **only after** internal recomputation confirms no violations.
- [ ] Recovery check: if any ambiguity in the case fields was encountered, confirm the chosen interpretation is consistent with prompt requirements (system-wide demand/reserve; no branch-flow modeling; reserve deliverability via headroom).
