# Locational Marginal Prices and Counterfactual DC-OPF Reporting (Dual-Based)

## Purpose
Compute and report nodal energy prices (LMPs) and reserve marginal clearing price (MCP) from an optimization-based DC-OPF (optionally with reserves), including a base case and a counterfactual case with a specified transmission limit change, while validating solver availability, units/sign conventions, and the final JSON artifact.

## When to Use
Use when a task requires (a) solving a DC-OPF or DC-OPF plus reserve procurement, (b) extracting LMPs and/or reserve MCP from dual variables, and (c) producing a machine-checked JSON report comparing a base run to a counterfactual run (for example, a line limit increase/decrease). Do not use for AC-OPF, nonconvex formulations, or cases where prices are defined by a market simulation not tied to optimization duals.

## Procedure
- 1) Discover the contract and inputs before modeling (no guessing)
- Locate the required input files and required output path from task instructions or repository files (README, starter code, tests).
- Identify the network data format (for example MATPOWER-like JSON) and confirm required fields exist: buses, generators, branches/lines, loads, cost data, baseMVA (or another unit reference), and any reserve requirement fields if reserves are in scope.
- Decision point: If the task specifies a target line (from_bus, to_bus) and a limit edit (for example +20%), verify the line exists (either direction) and that its limit field is present and numeric. If ambiguous (multiple parallel lines), select by a stable identifier if present; otherwise stop and request clarification rather than guessing.
- 2) Validate the modeling approach and toolchain (fail fast)
- Confirm the optimization library is available (for example, CVXPY) and list installed solvers via the library API. Select a solver from what is installed that supports:
- Continuous convex problems (QP or LP as needed by your cost model).
- Dual values for constraints.
- Fallback: If no suitable solver is available, perform a bounded, minimal install only if permitted by the environment; otherwise exit with a clear instruction listing missing packages/solvers.
- Checkpoint: Run a tiny sanity solve (a trivial convex problem) and confirm dual_value is returned for an equality/inequality constraint; if duals are None, switch solver or adjust solver settings before building the full model.
- 3) Build the base DC-OPF (and reserves if required) with explicit dual hooks
- Construct variables and constraints using discovered dimensions (never hard-code counts):
- Voltage angles (with one reference/slack angle fixed).
- Generator outputs (with min/max).
- Power balance at each bus; store each balance constraint object in an array for later dual extraction.
- Line flow constraints based on the chosen DC model; store each line limit constraint if congestion diagnostics are needed.
- If reserves are required: reserve variables, generator reserve limits, and a system reserve requirement constraint; store that constraint object for MCP extraction.
- Units: Keep one consistent unit system internally. Explicitly record whether variables are in per-unit or MW, and whether objective is in $/h, $/MWh, or another unit. Do not apply baseMVA scaling unless the input data and constraint definitions confirm per-unit usage.
- Solve the base problem and verify solver status indicates a valid optimum (or acceptable near-optimal status consistent with the chosen solver).
- Checkpoint: Confirm theta, generation, and (if present) reserve variables have finite values; confirm each stored constraint has a numeric dual_value (not None). If duals are missing, re-solve with a different installed solver or adjusted tolerances rather than filling in zeros.
- 4) Map duals to prices with a sign-and-scale check (do not assume conventions)
- Define the exact algebraic form used for each nodal balance constraint, for example:
- Form A: injection(bus) - withdrawal(bus) - net_export(bus) == 0
- Form B: injection(bus) - withdrawal(bus) == net_export(bus)
- Extract the raw dual for each bus balance constraint.
- Determine the LMP mapping (sign and scaling) by validation, not by memory:
- Execution anchor (finite-difference validation): Pick one bus, add a small epsilon to its load (or equivalently tighten its balance by epsilon in a consistent way), re-solve, and compute approx_marginal_cost = (obj_perturbed - obj_base)/epsilon in the same units as epsilon. Choose the LMP mapping (possibly sign flip and/or baseMVA scaling) so that LMP_bus approximately matches approx_marginal_cost within a reasonable tolerance (solver dependent). Repeat for a second bus if the first is inconclusive.
- Reserve MCP: Use the dual of the system reserve requirement constraint. If the constraint is clearly nonbinding (dual near zero within tolerance), report MCP as 0.0 and record that it was nonbinding by tolerance, not by assumption.
- 5) Run the counterfactual case with a controlled, auditable modification
- Apply only the task-specified modification (for example, increase a single line limit by a percentage). Record:
- Which line record was modified (identifier or endpoints plus index).
- Old limit and new limit.
- Rebuild or update the optimization model as needed to ensure the constraint actually changes (avoid in-place edits that do not affect the built constraints).
- Solve the counterfactual and repeat the same dual extraction and the same validated sign/scale mapping from step 4 (do not re-guess conventions).
- Compute deltas required by the task (for example, LMP drops, cost difference, congestion changes). If the task asks for top-k buses, sort using numeric values and include ties deterministically (stable sort by bus id as secondary key).
- 6) Write the report artifact and validate it against the discovered schema
- Determine the exact output path from the task contract (do not invent directories). Write JSON with only ASCII characters.
- Execution anchor (post-write validation):
- Re-open the file from the same path, JSON-parse it, and assert required top-level keys and nested fields match the task/starter schema (keys present, types correct, arrays/dicts shapes consistent, numbers finite).
- Also assert that the report includes both base and counterfactual results and that the recorded line modification matches what was applied.
- If validation fails, fix the producing code/data mapping and rewrite; do not proceed with an unvalidated artifact.

## Constraints / Pitfalls
- Never hard-code a solver name or assume dual sign/scale; always discover installed solvers and validate the LMP mapping with a finite-difference or equivalent consistency check before reporting prices.
- Do not write report.json to an assumed path and do not declare completion until you (a) verify the file exists at the task-specified location, (b) can parse it as JSON, and (c) pass a schema/key/type check derived from the task or starter artifacts.