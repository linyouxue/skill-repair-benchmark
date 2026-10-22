# verifier-aligned-unit-commitment-output-workflow

## Purpose
Produce a verifier-accepted unit-commitment style optimization artifact by first discovering the observable output contract (path, schema, and checker logic), then generating a feasible schedule using a solver only if the environment supports it, and finally enforcing a strict reload-and-validate gate where every reported field and pass/fail flag is recomputed from the written artifact exactly as the verifier expects.

## When to Use
Use when a task requires writing a machine-checked artifact (often JSON) representing a UC-like schedule (commitment, transitions, dispatch, reserves, costs/flags) that will be graded by an external verifier/test script. Do not use when the task has no external artifact-based grading, no explicit output path/schema requirements, or when only conceptual guidance is requested.

## Procedure
- 1) Discover the verifier-visible contract (hard gate; no guessing).
- Locate: (a) the required output path, (b) required format (JSON/CSV/etc), and (c) required keys/arrays by reading task instructions and searching the workspace for schema files and verifier/tests.
- If tests/verifier exist, extract the exact checks they perform (keys, shapes, tolerances, how violations are computed, any sentinel values).
- Decision point:
- If you cannot determine the required output path or required top-level schema/keys from any observable source, stop and request clarification (do not proceed with assumed UC conventions).
- 2) Validate inputs and normalize indexing to match the discovered contract.
- Load inputs from discovered locations; validate presence and types of all fields referenced by the contract/verifier (for time series: assert consistent T, numeric types, and list/array lengths).
- Normalize indices and semantics explicitly to the contract (examples that must be decided from contract/tests, not assumed): whether dispatch is total MW vs above-min, whether reserves are a per-time list, whether su/sd refer to transitions into period t, and how t=0 uses initial conditions.
- Execution checkpoint: print/record a compact schema summary (T, G, required arrays and their shapes) and stop if any required field is missing or ambiguous.
- 3) Establish an environment plan for producing a feasible schedule (solver vs fallback).
- Discover available tooling without making changes: check for installed MILP modeling/solver interfaces and/or solver binaries on PATH; record what is available.
- Decision point (policy-driven):
- If a MILP solver is available, proceed with MILP.
- If no solver is available:
- If the task/environment explicitly allows installing dependencies, install minimally and re-check availability.
- Otherwise, switch to a contract-compliant heuristic construction only if the contract permits (for example, if any feasible schedule is accepted and optimality is not required). If feasibility cannot be guaranteed without a solver, stop rather than emitting unverifiable outputs.
- 4) Generate the artifact and enforce verifier-aligned validation (final gate on the exact output path).
- Build the schedule using the chosen method while mirroring the contract-defined semantics (time indexing, initial conditions, reserve deliverability, ramp coupling, min up/down, cost definitions) only as specified/observable.
- Write the artifact to the required output path (do not silently choose a different path).
- Execution anchor (mandatory final gate):
- Reload the written artifact from the exact required path.
- Schema-validate: assert required keys exist; arrays are correct lengths; element types are numeric/boolean as required; no NaN/inf; units/conventions match the contract where checkable.
- Recompute every verifier-specified pass/fail check and summary metric from the reloaded artifact plus original inputs (not from internal solver state).
- Decision point:
- If any schema assertion or recomputed check fails, do not claim completion and do not set any "pass" flags; iterate by fixing modeling/extraction/serialization until the reloaded artifact passes all checks.

## Constraints / Pitfalls
- Never invent or assume verifier conventions (time semantics, reserve definitions, tolerances, cost formulas, required keys). If verifier/tests/schema cannot be found, stop instead of emitting a plausible UC report.
- Never declare success without a reload-and-validate pass on the exact required output path. Do not set any constraint_check/pass fields to "pass" unless they are computed from the reloaded artifact using the same rules the verifier uses.