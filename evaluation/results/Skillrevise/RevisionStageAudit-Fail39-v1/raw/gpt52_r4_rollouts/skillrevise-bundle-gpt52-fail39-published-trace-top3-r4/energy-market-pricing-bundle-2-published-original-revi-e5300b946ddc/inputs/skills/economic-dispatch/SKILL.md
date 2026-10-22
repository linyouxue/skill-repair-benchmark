# DC-OPF Market Clearing With Reserves (MATPOWER-Style)

## Purpose
Solve a DC optimal power flow (market-clearing) problem with optional reserve co-optimization using MATPOWER-style bus/gen/branch/gencost data, then extract dispatch, line flows, binding constraints, and nodal prices (LMPs) from solver duals in a verifier-aligned, schema-checked output artifact.

## When to Use
Use when the task requires an end-to-end DC-OPF (not just economic dispatch): network-constrained nodal balance, branch thermal limits, optional reserves, dual-based price extraction (LMP and reserve price), identifying binding generators/lines, and writing a machine-checked JSON report to a specified output path.

## Procedure
- 1) Environment preflight (before any modeling)
- Discover how code will run (python binary, working directory, writable locations).
- Execution anchor: run a minimal Python import/version probe for required packages you intend to use (at least: json; and if optimizing: numpy and cvxpy).
- If imports fail:
- If Python is externally managed (PEP 668) or pip install fails, create a local virtual environment (venv) in a writable directory, install only the missing packages, and re-run the probe.
- If you cannot create a venv or install packages, stop and switch to a simpler available solver/toolchain only if already present; otherwise abort with a clear missing-tool report (do not keep guessing commands).
- 2) Load inputs and validate schema and dimensions (before constraints)
- Load the task-provided input file(s) (often JSON) and locate MATPOWER-style arrays/fields.
- Validate presence and minimum shapes:
- bus: must include IDs and PD load column(s) needed for DC balance.
- gen: must include GEN_BUS, PMAX, PMIN columns.
- branch: must include from/to buses, reactance (or data to derive susceptance), and candidate rate columns (RATE_A/B/C if present).
- gencost: must include MODEL, NCOST, and coefficients.
- Validate indexing assumptions:
- Confirm whether bus numbers are 1-indexed and whether they are contiguous; if not contiguous, build an explicit bus-number-to-index map and use it everywhere.
- Thermal limit field discovery (do not assume RATE_A):
- If multiple rate columns exist (A/B/C or equivalents), compute simple summaries (count of >0 entries, min/median/max, and outlier ratio).
- Choose the active limit field using a deterministic rule you can justify from data, for example:
- Prefer the column with the highest fraction of positive finite values and a plausible magnitude range relative to typical flows (avoid columns that are mostly zeros or have extreme outliers).
- If selection remains ambiguous, require clarification (or run both as separate scenarios only if the task explicitly allows).
- Checkpoint: confirm the specific contingencies/counterfactual edits requested by the task can be located (e.g., target line identified by endpoints and in-service status). If not found uniquely, stop and ask for disambiguation.
- 3) Build the DC network model using discovery, not hard-coded formulas
- Derive the DC susceptance model from branch data:
- Compute series susceptance b = 1/x for each in-service line where x is nonzero; guard against zero/near-zero reactance (abort or filter with an explicit rule).
- Incorporate tap ratios and phase shifters only if those fields exist and are nontrivial; otherwise treat as 1 and 0 (do not assume presence).
- Construct nodal balance constraints:
- Decision variables: bus voltage angles (theta) and generator outputs (Pg). Optionally reserves (Rg).
- Fix a reference bus angle (slack) to 0 at a discovered reference bus (explicitly choose one bus index deterministically).
- Enforce power balance at each bus: sum(Pg at bus) - Pd(bus) = net injection implied by DC flows.
- Construct branch flow expressions and enforce thermal limits using the selected limit field:
- For each in-service branch: -Fmax <= F <= Fmax, with Fmax from the discovered rate column (skip or mark unconstrained only if the value is missing/zero and the task permits).
- Add generator limits and reserve coupling if reserves are in scope:
- PMIN <= Pg <= PMAX
- Rg >= 0; optionally Rg <= Rcap if provided
- Pg + Rg <= PMAX (in consistent units)
- 4) Define objective and solve with bounded solver fallback
- Objective: minimize total production cost using gencost:
- Validate gencost MODEL and NCOST per generator before building terms.
- Support at least linear and quadratic polynomial costs; if higher order appears, either implement generically or abort explicitly (do not silently truncate).
- Solve using a bounded fallback order:
- Attempt available solvers in an ordered list you discover from the environment (e.g., CLARABEL, OSQP, SCS), with time/iteration limits.
- After each attempt, record status (optimal/optimal_inaccurate/infeasible/unbounded/error).
- If a solver errors or hits limits, try the next solver; do not loop indefinitely.
- If status is infeasible:
- Run a minimal diagnosis checklist before changing the model:
- Verify total load is within sum(PMAX) and above sum(PMIN).
- Verify selected branch limits are not all near-zero or missing.
- Verify units consistency (MW vs per-unit) and that limits and variables share units.
- Controlled feasibility-restoration fallback (only if task allows and you label it):
- Add a nonnegative load-shedding slack with a very large penalty, or add bounded line-overload slack with a very large penalty.
- Re-solve once to obtain a diagnostic solution; report slack usage explicitly and do not present it as a valid base-case unless permitted.
- 5) Extract prices and binding constraints (post-solve checks)
- LMP extraction:
- Identify the dual variables associated with nodal power balance constraints.
- Apply a consistent sign convention check:
- Perturb a single bus load by a small amount (or reason from constraint form) to confirm that LMP increases when load increases; if sign is flipped, multiply by -1.
- Reserve price (if reserves):
- Extract dual of the system reserve requirement constraint as the reserve marginal clearing price; verify nonnegativity if the model implies it.
- Binding elements:
- Lines: mark as binding if abs(|F| - Fmax) <= tolerance.
- Generators: mark if Pg at PMIN/PMAX within tolerance; reserves similarly if Rg at bounds.
- Checkpoint: ensure all reported numeric outputs are finite (no NaN/inf) and that power balance residuals are within tolerance.
- 6) Write outputs to verifier-visible paths and validate by reloading (finalization)
- Determine required output path(s) from the task statement; do not invent filenames. If not specified, stop and request the required path.
- Write JSON using only standard, portable serialization (no custom encoders).
- Execution anchor: reopen the written file(s), parse JSON, and assert:
- Required top-level keys exist (as specified by the task or discovered schema requirements).
- Arrays have expected lengths (n_bus, n_gen, n_branch as applicable).
- All prices/dispatch/flows are finite numbers and consistent units are labeled.
- Only after these checks pass, declare completion.

## Constraints / Pitfalls
- Do not assume MATPOWER column meanings, rate fields, solver availability, or package availability without discovery and validation; always log chosen interpretations (e.g., which branch rate column is treated as thermal limit).
- Do not apply feasibility-restoration (load shedding or overload slack) silently; it must be a single bounded diagnostic fallback, clearly labeled, and never substituted for a valid base-case solution unless the task explicitly allows it.