# Locational Marginal Prices (LMPs) from DC-OPF

## Purpose
Extract nodal LMPs and reserve clearing prices from a solved DC-OPF as duals of the balance and reserve constraints, and run counterfactual congestion-relief analyses with verifiable sign, scale, and binding checks.

## When to Use
Any task that computes nodal electricity prices, reserve MCP, binding transmission lines, or price-impact of relaxing a transmission limit from a DC-OPF formulation in a convex solver.

## Procedure
- Discover inputs: inspect bus, generator, and branch tables for columns actually present (bus id, Pd, gen cost, x, rate, tap ratio, phase shift, baseMVA). Record which optional fields exist; do not assume defaults.
- Build network: construct Bbus and branch susceptance using b_eff = 1/(x*tap if tap>0 else 1); carry phase-shift angle_offset into flow = b_eff * (theta_f - theta_t - angle_offset). Validate matrix shapes against n_bus, n_branch.
- Formulate OPF: write the nodal power balance in per-unit (your chosen form, scalar or vectorized) and store a reference to each balance constraint (or the single vector constraint) before adding to the problem. Store the reserve requirement constraint reference separately if present.
- Solve and gate: call solver; verify status is optimal. If not, abort and report; do not read duals from a non-optimal solution.
- Verify duals (execution anchor): pick an unconstrained reference bus (no binding line incident) and compute expected LMP = marginal cost of its dispatched generator in $/MWh. Compare to raw_dual, raw_dual*baseMVA, -raw_dual*baseMVA, -raw_dual/baseMVA and select the transform matching within tolerance. Apply the same transform to all buses. If no transform matches, report inconsistency instead of guessing.
- Report reserve MCP: use the stored reserve constraint's dual with the sign convention of its inequality direction; explicitly flag whether the constraint binds (dual != 0 and reserve sum == requirement).
- Identify binding lines: compute loading_pct = |flow_MW|/rate*100 using b_eff and angle_offset; flag lines with loading_pct >= configured threshold (default 99%).
- Counterfactual: locate the target branch by matching endpoint pair in either direction; error if not found. Modify its rate, re-solve, re-run the verify-duals checkpoint, and report delta_cost, delta_LMP per bus, and whether each previously binding line is now unbinding.

## Constraints / Pitfalls
- Do not hard-code the mapping from raw dual to $/MWh; derive it per run from the sanity check in the Verify-duals step. Sign and scale depend on constraint orientation (gen-load vs load-gen), per-unit vs MW RHS, and inequality direction.
- Negative LMPs and zero reserve MCPs are valid outcomes; always report the binding status alongside the price so a zero or negative value is not mistaken for an error.
- Never ignore tap ratio or phase shift when either column is present and non-default; omitting them silently corrupts flow and binding detection.
- Do not read dual_value when solver status is not optimal, or when the constraint reference was not stored prior to solving.
- Keep the binding threshold, tolerance for the sign-check, and the counterfactual scaling factor as named parameters, not inline literals.