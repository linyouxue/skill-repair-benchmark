# unit-commitment-milp-verifier-aligned-workflow

## Purpose
Produce a feasible and verifier-consistent mixed-integer linear unit-commitment style schedule (commitment, startups/shutdowns, dispatch, reserves, renewables) by (1) discovering the task's required report contract, (2) building a UC MILP with correct time indexing and initial conditions, and (3) validating feasibility and reported fields by recomputing checks from the final report arrays (not from internal solver state).

## When to Use
Use only when the task requires an end-to-end UC-style optimization output that will be graded by an external verifier reading a written artifact (typically JSON) containing time-series schedules, costs/summaries, and constraint-check fields. Do not use for generic MILP advice, non-UC MILPs, or tasks without a machine-checked report contract; in those cases use a simpler solver/runbook skill.

## Procedure
- 1) Discover the observable contract (do this before modeling).
- Locate task files and required output path(s) via repository search (do not assume fixed paths).
- Identify the required report schema/keys by reading: README/instructions, any provided schema files, and any verifier/test code.
- Checkpoint evidence: you can list required arrays (names, shapes, units), required summary fields, and how the verifier computes each pass/fail check. If any are unclear, stop and ask for clarification or inspect more files; do not guess.
- 2) Normalize inputs and define index conventions (make time semantics explicit).
- Parse inputs into deterministic arrays with explicit indices: generators g=0..G-1, time t=0..T-1.
- Define, in writing, the meaning of each decision:
- u[g,t] in {0,1} commitment (online status at t).
- su[g,t], sd[g,t] in {0,1} startup/shutdown indicator for transitions between t-1 and t (define whether su at t refers to turning on at start of period t).
- p[g,t] >= 0 dispatch in MW (total output, not "above-min", unless the contract explicitly says otherwise).
- r[g,t] >= 0 reserve provided (and any renewable spillage/curtailment variables if needed).
- Checkpoint evidence: print shapes and confirm they match the contract (T alignment, per-generator parameters present). If any parameter is missing, stop and add a safe default only if the contract explicitly allows it.
- 3) Pre-solve sanity checks (execution anchor: stop early on impossible inputs).
- For each time t, compute a conservative upper bound on achievable supply using only input limits (no MILP):
- max_supply[t] = sum_g Pmax[g] + renewable_max[t] (or other sources per contract), adjusted by any hard outages if present.
- required[t] = demand[t] + reserve_requirement[t] (if reserve is required by contract).
- If any t has max_supply[t] < required[t] (optionally with a small tolerance), stop: report "input infeasible" and do not build a MILP that will only return infeasible.
- Checkpoint evidence: a list of failing periods (if any) and the computed bounds.
- 4) Build the UC MILP with a deterministic variable map and UC-specific constraint templates.
- Create a deterministic variable map (single allocator; no scattered index arithmetic).
- Add constraints in this order (each family must be mirrored by a later validator check):
- Variable bounds and integrality.
- Transition linking with explicit t=0 handling:
- For t>0: su[g,t] - sd[g,t] = u[g,t] - u[g,t-1] (or equivalent), plus su+sd <= 1 if required.
- For t=0: use initial status u0[g] (from inputs) in the same equation; do not invent u[-1].
- Dispatch feasibility:
- If u[g,t]=0 then p[g,t]=0 (enforced via p <= Pmax*u and p >= Pmin*u when Pmin exists).
- Ensure the model matches the contract's definition of p (total MW vs above-min).
- Demand and reserve balance:
- Sum_g p[g,t] + renewables_used[t] (as defined) meets demand.
- Sum_g r[g,t] meets reserve requirement if applicable.
- Joint capability and deliverability:
- p[g,t] + r[g,t] <= Pmax[g]*u[g,t] (and >= Pmin*u if applicable).
- Ramp/deliverability constraints must match contract (e.g., reserve deployable within ramp-up): encode using p and r and correct time coupling.
- Minimum up/down time with initial conditions:
- Use a standard formulation keyed off su/sd, explicitly incorporating initial on/off durations if provided.
- If initial duration data is absent, do not guess obligations; instead implement only what the contract/data supports and record the assumption.
- Startup/shutdown costs and any multi-tier logic:
- Implement only if the contract or input data defines the tier mapping unambiguously; otherwise keep costs simple and avoid adding feasibility-impacting constraints.
- Checkpoint evidence: for each constraint family, you can point to (a) the input parameters used and (b) the corresponding validator function/check that will recompute it from the report.
- 5) Solve safely and decide what to do based on solver outputs.
- Discover available solver interfaces in the environment (do not assume a specific package). Prefer a MILP-capable open-source solver present in the environment.
- Set a time limit and request an incumbent.
- Decision point:
- If no incumbent solution exists, stop and debug the model; do not emit a report claiming feasibility.
- If time-limited but incumbent exists, proceed to validation but mark solver status accordingly.
- Constraint: only report a MIP gap if it is directly provided by the solver API as a valid relative gap; otherwise set it to null/empty per schema (never invent).
- 6) Extract schedules and run verifier-aligned validation (execution anchor: report-driven gate).
- Extract arrays from the incumbent without post-hoc "fixing" (no rounding binaries unless within a strict tolerance and you re-validate after rounding).
- Build the report object in the contract's exact units and conventions.
- Run a validator that recomputes, from the report arrays plus original inputs (not internal solver rows):
- transition consistency (u, su, sd, including t=0 with u0),
- min up/down windows,
- dispatch bounds (Pmin/Pmax with u),
- ramp and reserve deliverability,
- demand balance and reserve satisfaction,
- objective/cost recomputation consistency (within tolerance if required).
- Decision point:
- If any check fails or any required summary metric disagrees with recomputation, do not set any "pass" flags; return to modeling/extraction and fix the root cause.
- Only after all checks pass, set constraint_check fields to "pass" (or schema-equivalent) and populate summary fields from the validator outputs.
- 7) Write, reload, and finalize.
- Write the report to the required output path.
- Reload the written artifact and rerun the report-driven validator on the reloaded data (guards against serialization/schema mistakes).
- Checkpoint evidence: validator returns all_pass=true on the reloaded artifact; only then claim completion.

## Constraints / Pitfalls
- Never "cosmetically" overwrite violation metrics or set constraint checks to "pass" without recomputing them from the final report arrays. If the validator shows nonzero violations, the report must reflect that or the schedule must be fixed.
- Do not hard-code time indexing, t=0 transition behavior, or whether dispatch is total MW vs above-min. These are frequent verifier-mismatch causes; always derive conventions from the observable contract and inputs, and encode t=0 explicitly using provided initial conditions.