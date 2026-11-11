# unit-commitment-operating-rules

## Purpose
Produce verifier-aligned outputs for day-ahead or multi-period unit commitment (UC) tasks by using discovery-first environment grounding, generating a feasible schedule in the required report format, and validating the artifact against the task's observable schema and checks before finalizing.

## When to Use
Use when a task requires emitting a UC schedule/report (commitment, dispatch, reserves, costs, checks) that will be graded by an external verifier or validator. Do not use when the task is purely conceptual, asks only for equations, or does not require writing a verifier-consumed artifact.

## Procedure
- 1) Preflight discovery (do this before modeling or writing files)
- Locate the contract sources in the current workspace: task README/instructions, validator/verifier script, sample output files, or tests.
- Extract and record:
- required output file path(s) (exact location the verifier reads),
- required output format (JSON/CSV) and required keys/fields,
- required dimensions (time horizon T, generator lists, indexing rules),
- any explicitly defined checks (names and their computed quantities).
- Decision point:
- If a repo-provided runner/solver exists (scripts, notebooks, Makefile targets), use it as the primary path.
- Only if no such tooling exists, proceed to implement a minimal solver/constructor yourself.
- 2) Input and convention normalization (before any irreversible solve)
- Load the input data and validate basic integrity: all required entities exist (generators, periods, demand, limits), no missing arrays, and every time series has consistent length T.
- Choose exactly one production convention and document it in code:
- actual MW output, or
- above-minimum MW output.
- Checkpoint: confirm initial conditions needed by the checks are present (initial on/off status, initial output, prior on/off durations). If any are missing or ambiguous, stop and request clarification or infer only if the contract explicitly specifies an inference rule.
- 3) Generate a candidate schedule using the lightest environment-supported method
- Prefer: run the discovered native solver/entrypoint and capture its outputs.
- Else: construct a schedule using the smallest method that can satisfy the discovered checks (do not overbuild):
- enforce offline implies zero production and zero reserve,
- enforce min/max output when online,
- enforce demand balance per period using the contract's definition,
- enforce reserve requirement and deliverability using the contract's definition,
- enforce transition logic using initial status,
- enforce ramping using initial output and the chosen production convention,
- enforce minimum up/down time only if it is part of the discovered check set.
- Decision point: if any constraint family is not defined in the discovered contract, do not invent it; treat it as out of scope unless the task instructions explicitly require it.
- 4) Write, reload, and verify the artifact (finalization gate)
- Write the report to the exact discovered required output path(s). Do not silently change paths.
- Execution anchor: reload the written artifact from that same path and perform:
- schema/type/shape validation (required keys present, types correct, arrays length T, entity IDs match input lists),
- verifier-aligned recomputation of checks using the discovered definitions (or, if definitions cannot be found, report checks as unknown rather than "pass").
- Only after these validations:
- populate any check fields according to the recomputation results (never blanket "pass"),
- populate solver status fields only if backed by observable solver output; otherwise use a conservative status (for example, "feasible") and leave optimality/gap fields unset or null if not explicitly provided by the tool.

## Constraints / Pitfalls
- Do not build a custom MILP/optimizer until you have searched for and ruled out repo-native solver/validator tooling and have extracted the required output schema and output path; overbuilding increases verifier mismatch risk.
- Never set check fields to "pass", claim "optimal", or report a zero gap unless you (a) can recompute the corresponding check using the verifier-defined formulas and (b) can cite the solver-produced evidence for optimality/gap; if the contract is not discoverable, emit unknown/omitted check statuses rather than false certainty.