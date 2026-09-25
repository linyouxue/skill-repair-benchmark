# SKILL.md

## When to use
Use this skill when you must run **two comparable market-clearing optimizations** on the *same* power system snapshot (MATPOWER-style data in a JSON file), where the second run is a **counterfactual sensitivity** that modifies **one specified transmission line thermal capacity by a fixed percentage**. The required deliverable is a machine-readable `report.json` summarizing:
- each scenario’s **total cost**, **LMPs by bus**, **reserve market clearing price**, and **binding/near-binding lines**
- a structured **impact comparison** (cost delta, top LMP drops, and whether congestion is relieved per the task’s definition)

Before acting, gather evidence from the task context and input file for:
- how buses, generators, loads, and branches/lines are represented in the MATPOWER JSON
- where **branch thermal limits** are stored and how to uniquely identify the specified line (directionality, multiple circuits, parallel lines)
- reserve requirement and coupling definitions needed for “reserve co-optimization” (or what fields in the data indicate them)

## Possible Failure Modes
- **Editing the wrong branch**: misidentifying the target line due to reversed from/to ordering, parallel lines, transformer records, or indexing differences between MATPOWER tables and JSON arrays.
- **Not keeping scenarios identical** except for the single capacity increase (e.g., accidentally changing baseMVA, loads, generator limits, or reserve parameters).
- **Incorrect thermal limit interpretation**: confusing rateA/rateB/rateC; using percent loading on the wrong base; mixing MW vs per-unit.
- **Producing LMPs without duals**: computing nodal prices incorrectly (e.g., using average system price) instead of extracting **nodal balance constraint duals** from the DC-OPF.
- **Reserve MCP mis-defined**: using generator reserve offers directly or averaging shadow prices rather than using the **dual of the system reserve requirement** consistent with the formulation.
- **Binding line detection mismatch**: failing to apply the “near thermal capacity” rule (loading ≥ 99%) or reporting flows without sign/absolute value consistency against limits.
- **Counterfactual infeasibility**: solver fails due to formulation bugs; returning partial results instead of diagnosing and recovering (e.g., checking data validity, slack bus, connectivity).
- **Impact analysis mistakes**: wrong sign for deltas, selecting largest absolute changes instead of “largest drop,” or mixing up base vs counterfactual when ranking.
- **Ambiguous congestion flag logic**: misreading the task’s definition of “congestion_relieved” (ensure your boolean matches the contract’s stated interpretation, even if wording is awkward).
- **Output format drift**: missing required keys, wrong numeric types, omitting some buses, or not writing `report.json` exactly as specified.

## Possible procedures
1. **Ingest and normalize the network snapshot**
   - Load `network.json` and locate MATPOWER-equivalent tables/fields (bus, gen, branch, gencost, etc.).
   - Confirm units (baseMVA) and branch limit fields; decide whether flows/limits will be handled in MW.
   - Build stable identifiers for branches (from bus, to bus, circuit id if present).

2. **Construct the base DC-OPF + reserve co-optimization model**
   - Decision variables (typical):
     - generator real power dispatch (Pg)
     - bus voltage angles (θ) with a single reference bus fixed
     - line flows (or compute from θ using susceptance)
     - spinning reserves per generator (R) if co-optimized
   - Constraints (as required by contract):
     - nodal power balance (DC)
     - generator operating limits (include any “temperature limits” fields as provided; interpret as min/max or ramp/thermal limits per dataset encoding)
     - branch thermal limits on flows
     - spinning reserve requirement (system-wide or zonal, per data)
     - “standard capacity coupling” between energy and reserve (e.g., Pg + R ≤ Pmax; and R ≤ reserve capability)
   - Objective: minimize total cost (energy cost + reserve cost if modeled) using provided cost curves/bids.

3. **Solve and extract market outputs (base case)**
   - Run the LP/QP solver.
   - Extract:
     - `total_cost_dollars_per_hour` directly from objective value (ensure hourly interpretation matches data)
     - `lmp_by_bus`: use dual variables of nodal balance constraints (with correct sign convention); store one entry per bus
     - `reserve_mcp_dollars_per_MWh`: use the dual of the reserve requirement constraint (again sign/units consistent)
     - `binding_lines`: compute flow on each branch and mark those with `abs(flow) / limit ≥ 0.99`; report flow and limit in MW with correct from/to labeling
   - Evidence checks:
     - power balance residuals near zero
     - at least one slack/reference angle fixed
     - no constraint violations beyond tolerance

4. **Create the counterfactual case**
   - Copy the base case data/model inputs.
   - Locate the specified transmission element and increase its thermal capacity by the required percentage.
   - Do not alter any other parameters.
   - Re-solve and extract the same outputs as above.

5. **Compute impact analysis**
   - `cost_reduction_dollars_per_hour`: base_cost − counterfactual_cost (confirm sign matches “reduction”)
   - `buses_with_largest_lmp_drop`:
     - join base and counterfactual LMPs by bus
     - compute delta = cf_lmp − base_lmp
     - select the three most negative deltas (largest drops), and include base, cf, and delta
   - `congestion_relieved`:
     - implement exactly per contract’s definition using the counterfactual binding status of the adjusted line; if the definition is ambiguous, add a small internal note to yourself and choose the interpretation that matches the stated “true indicates …” clause.

6. **Write `report.json`**
   - Ensure JSON structure and key names match the contract.
   - Keep numeric fields as JSON numbers (not strings).
   - Include all buses in each `lmp_by_bus` list unless the contract explicitly allows omission.

## Verification Checklist
- [ ] Loaded `network.json` successfully and identified bus/gen/branch data and relevant limit/cost fields without guessing hidden inputs.
- [ ] Base and counterfactual models are identical except for the single specified line’s thermal capacity increase by the required percentage.
- [ ] The modified line is uniquely and correctly identified (validated by matching endpoints and any available circuit/index metadata).
- [ ] Both optimizations solved to optimality (or documented/handled infeasibility with a recovery attempt rather than emitting junk values).
- [ ] `lmp_by_bus` contains one entry per bus with LMPs derived from **nodal balance duals** using consistent sign/units.
- [ ] `reserve_mcp_dollars_per_MWh` is derived from the **reserve requirement** dual and has consistent units.
- [ ] `binding_lines` uses the contract threshold (loading ≥ 99%), with flow magnitude compared to the correct limit and consistent from/to labeling.
- [ ] Impact metrics:
  - [ ] `cost_reduction_dollars_per_hour = base − counterfactual`
  - [ ] Top 3 buses selected by **largest LMP drop** (most negative delta), and each record contains base, counterfactual, and delta with consistent sign.
  - [ ] `congestion_relieved` matches the contract’s stated criterion (do not substitute your own definition).
- [ ] `report.json` is valid JSON, matches the required schema/key names, and does not include extraneous fields.
- [ ] No concrete values, IDs, or implementation artifacts were copied from retrieved examples; unrelated files/state are not modified beyond producing `report.json`.
- [ ] If any evidence in the input data is ambiguous (units, limit field choice, line identification), you performed a targeted sanity check (e.g., compare computed flows vs limits; verify LMP patterns) and corrected before finalizing.
