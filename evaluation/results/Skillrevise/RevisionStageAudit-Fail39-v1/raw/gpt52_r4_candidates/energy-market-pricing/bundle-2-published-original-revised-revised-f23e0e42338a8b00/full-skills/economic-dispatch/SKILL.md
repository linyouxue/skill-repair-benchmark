# DC-OPF Market Clearing With Verifier-Aligned Branch Rating Conventions

## Purpose
Solve a DC optimal power flow (DC-OPF) market-clearing problem (optionally with reserves) from MATPOWER-style data, while explicitly aligning any branch thermal-limit convention (e.g., RATE_A vs RATE_B/C) to the task/verifier contract or, when ambiguous, producing guarded multi-scenario outputs that prevent incorrect certainty about congestion, binding constraints, and LMP impacts.

## When to Use
Use when you must compute network-constrained dispatch, line flows, and nodal prices from bus/gen/branch/gencost inputs, and the evaluator may assume a specific branch rating column or other subtle conventions that materially change which constraints bind and what prices result.

## Procedure
- 1) Environment and tool preflight (no irreversible actions)
- Discover runtime (python path, cwd, writable directory).
- Probe imports you will use (at minimum: json; for optimization: numpy and an optimizer such as cvxpy).
- If optimization packages are missing, only install if the environment permits (venv in a writable location). If you cannot install, stop with a missing-tool report rather than guessing alternative commands.
- 2) Load inputs and validate core schema (before modeling)
- Load task-provided input artifacts and locate MATPOWER-style arrays/fields (bus, gen, branch, gencost, plus any reserve requirement fields if applicable).
- Validate minimal columns and shapes needed for DC balance, generator bounds, branch endpoints, and reactance/susceptance.
- Build an explicit bus-number to internal-index map if bus IDs are not contiguous or not 1..n.
- Identify candidate branch rating columns from the input (commonly RATE_A, RATE_B, RATE_C, or task-specific equivalents). Do not assume a single column exists or is correct.
- 3) Verifier-contract alignment for branch thermal limits (decision point)
- Contract discovery:
- Search the task statement, provided README, tests, or verifier notes for explicit conventions such as "use RATE_A", "use emergency rating", "use short-term rating", or "ignore zeros".
- If an explicit convention is found, record it as limit_convention and use it.
- If no explicit convention is found and multiple candidate rating columns exist:
- Execution anchor (diagnostics): compute and record for each candidate rating column:
- fraction of finite positive values, count of zeros, median, p95, and max
- Ambiguity rule:
- If two or more candidates are broadly viable (e.g., all have near-identical positive fractions and plausible distribution), treat the convention as ambiguous.
- If exactly one candidate is clearly viable (others are mostly zeros/non-finite), select the viable candidate and record why.
- If ambiguous:
- If the task allows multi-scenario outputs, solve a scenario per candidate rating column and carry all results forward.
- If the task requires a single answer and does not allow multi-scenario outputs, stop and request clarification rather than choosing arbitrarily.
- 4) Build and solve DC-OPF (per selected scenario)
- For each scenario (single or multiple):
- Build DC model with discovered data:
- Variables: generator outputs Pg; bus angles theta; optional reserves R if required.
- Choose and fix a reference bus angle deterministically (e.g., smallest bus ID in-service) and record it.
- Nodal balance at each bus using the bus-index map (no implicit contiguous indexing).
- Branch flows from susceptance b = 1/x with guards for x near zero; incorporate tap/phase shift only if fields exist and are non-default.
- Enforce thermal limits using the scenario's selected rating column and only for in-service branches; explicitly define how missing/zero limits are treated (skip only if contract allows; otherwise treat as an error).
- Generator limits and reserve coupling if in scope.
- Solve using a discovered solver availability order with time/iteration limits; record solve status and objective value.
- If infeasible, run only non-destructive diagnostics first (load vs sum(PMAX)/sum(PMIN), units consistency, limits sanity). Add feasibility slacks only if the task allows and label the solution as diagnostic, not final.
- 5) Post-solve extraction with guarded conclusions (per scenario)
- Extract dispatch, flows, and duals for:
- Nodal balance constraints (LMPs): apply a sign check (small perturbation or constraint-form reasoning) and record the sign convention used.
- Reserve requirement (if any): extract reserve price dual and record constraint name and sign convention; do not report a value without confirming which constraint dual it came from.
- Identify binding constraints with a declared numeric tolerance and record the tolerance used.
- Ambiguity guard (hard checkpoint):
- If multiple rating scenarios were solved, compare whether task-critical assertions (e.g., which line binds, whether congestion is relieved, price deltas) are invariant across scenarios.
- If not invariant, do not emit a single definitive claim; instead mark conclusions as scenario-dependent and include per-scenario outcomes.
- 6) Write output artifact and enforce schema via reload-and-assert (finalization gate)
- Write to the task-specified output path(s). If no output path is provided, stop and request it.
- Output must include, at minimum:
- limit_convention metadata: explicit_contract or inferred_ambiguous
- Either limit_column_used (single scenario) or scenarios[] each with limit_column_used
- For each scenario: solve status, objective, Pg, flows, LMPs, and binding flags/tolerance
- ambiguity_status describing whether conclusions are invariant
- Execution anchor (reload-and-assert): reopen the written file, parse JSON, and assert:
- metadata keys exist (limit_convention, ambiguity_status, and limit column fields)
- scenario count matches the ambiguity handling decision
- numeric arrays have consistent lengths and contain finite numbers
- no definitive congestion/binding claim is present unless either (a) the contract specified the convention, or (b) invariance across scenarios is demonstrated

## Constraints / Pitfalls
- Never hard-code a single branch rating column (e.g., RATE_A) unless the task/verifier explicitly states it or diagnostics prove other candidates are invalid; if candidates are viable and differ materially, treat this as ambiguity and branch to multi-scenario or clarification.
- Do not declare "binding line", "congestion relieved", or "LMP change" as a single fact when results vary across plausible rating conventions; instead gate such claims on contract alignment or cross-scenario invariance proven by a recorded comparison.