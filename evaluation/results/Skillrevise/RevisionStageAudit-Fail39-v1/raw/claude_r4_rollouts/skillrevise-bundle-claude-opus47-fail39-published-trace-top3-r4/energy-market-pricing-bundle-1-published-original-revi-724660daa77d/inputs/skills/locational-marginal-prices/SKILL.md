# Locational Marginal Prices (LMPs) from DC-OPF Duals

## Purpose
Extract nodal LMPs and reserve clearing prices from a solved DC-OPF by reading dual values of the stored equality/inequality constraints, deriving the correct sign and unit scaling from the actual constraint form, and validating prices against a known marginal cost before finalizing any artifact.

## When to Use
Use for any task requiring nodal electricity prices, reserve MCPs, congestion analysis, or counterfactual transmission studies from a DC-OPF formulated in a convex solver (e.g. CVXPY). Applies regardless of whether the balance constraints are written per-bus or vectorized.

## Procedure
- Discover task parameters from the instruction: input case file(s), required output path(s) and schema, target line(s) for counterfactuals, limit multiplier, binding-loading threshold, cost model (linear/quadratic/piecewise), and tolerance. Do not assume defaults; if a value is absent, record it as unknown and pick a conservative explicit value.
- Build the DC-OPF in whatever formulation is natural (per-bus or vectorized). Before calling solve, keep a Python handle to: (a) each nodal power balance constraint (or the single vector balance constraint), and (b) the reserve requirement constraint if present. Confirm units: write balance in per-unit on baseMVA and cost in $/hr with Pg in per-unit, OR in MW; document which.
- Solve and verify solver status is `optimal` (or solver-specific equivalent). If status is not optimal or any dual is `None`, retry with an alternative solver (e.g. switch among CLARABEL, SCS, ECOS, MOSEK if available) and record which one succeeded. Do not proceed with None duals.
- Derive LMP scaling by unit analysis, not by rote: if the balance constraint is in per-unit (Pg_pu - Pd_pu == ...), then dual has units of $/pu-MW/hr, so LMP in $/MWh is `dual / baseMVA`. If the balance is written in MW, LMP is `dual` directly. Sign depends on the convention: for `generation - load == flow_out` written as `lhs == rhs` with CVXPY, LMP = +dual/scale; for `load - generation == -flow_out` it flips. Resolve this by the next step rather than by assumption.
- Execution anchor (marginal-cost cross-check): pick a generator with `0 < Pg* < Pmax` that is not at a congested bus; its bus LMP should approximately equal its incremental marginal cost (derivative of its cost at Pg*). Assert `abs(LMP_bus - MC_gen) / max(1, MC_gen) < 0.05`. If it fails, try flipping sign, then rescaling by baseMVA, then both; adopt whichever combination passes and apply uniformly to every bus. Print the chosen (sign, scale) decision.
- Compute reserve MCP from the dual of the reserve requirement constraint using the same unit-analysis + sign-check logic: for a `sum(Rg) >= R_req` constraint the MCP should be non-negative; if your extracted value is negative, flip sign.
- Identify binding lines using the threshold parsed from the task (fallback: 99% loading if unspecified). Record each binding line's from/to bus, flow, and limit.
- For counterfactual analysis: parse target line(s) and multiplier from the task; modify only the specified entries; resolve; diff cost and LMPs. Assert `base_cost - cf_cost >= -tol` when a binding line is relaxed; otherwise flag the result.
- Write the output artifact in exactly the schema the task specifies. Then reload the file from disk and assert: required keys present, LMPs are finite floats in a plausible band (e.g. |LMP| < 1e5 unless the task implies otherwise), reserve_mcp sign matches the inequality direction, and counterfactual cost delta sign is consistent.

## Constraints / Pitfalls
- Do not hardcode `lmp = dual * baseMVA` or `lmp = -dual / baseMVA`. Derive scale from the constraint's units and resolve sign via the marginal-generator cross-check anchor.
- Do not bake in literals (99% threshold, 20% multiplier, polynomial cost assumption). Read them from the task instruction and fall back only with an explicit logged default.
- Store constraint references before calling `solve`; CVXPY duals are only accessible via the original constraint object.
- Never report prices when solver status is not optimal or when any required dual is None; retry with an alternate solver first.
- Negative LMPs can be physically valid (congestion), so do not use sign alone to detect an error; rely on the marginal-cost cross-check.
- The reload-and-assert post-write check is mandatory before claiming completion; a plausible-looking in-memory result is not sufficient evidence.