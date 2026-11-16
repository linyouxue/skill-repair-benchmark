# Verifier-Aligned OPF Market Report Writer (Minimal-Dependency, Schema-Gated)

## Purpose
Produce a verifier-ready JSON report (for DC-OPF market clearing, optionally with reserves and base vs counterfactual comparison) by (1) discovering the exact required output protocol and schema from the task environment, (2) selecting an environment-supported solve route with bounded setup, and (3) writing and validating `report.json` at the verifier-visible path with strict schema checks.

## When to Use
Use when a task asks for a specific JSON artifact (commonly `report.json`) summarizing OPF/market outcomes and comparisons, and the runtime may be a minimal Python environment with restricted package installation and a strict verifier that checks exact file paths and JSON structure.

## Procedure
- 1) Contract and environment discovery (no installs, no irreversible actions)
- Locate the task-declared required output filename/path and the required JSON structure:
- Search the task statement, README, and any visible tests/config for the exact output path (for example, `report.json`) and the required keys/types.
- If the output path is not explicitly stated, discover how the verifier locates outputs (for example, by scanning the working directory or a declared output directory). Record the discovered rule.
- Dependency preflight (execution anchor):
- Attempt imports in this order: `json` (required), then optional numeric/optimization deps (for example `numpy`, `scipy`, `cvxpy`, any solver libs).
- Decide the solve route within a small fixed time budget:
- Route A (preferred): use already-available installed solver stack.
- Route B (fallback): if no solver stack is available, do not attempt long installs. Only attempt a single lightweight alternative if it is already present (for example, a bundled CLI/tool provided by the environment).
- If neither route is possible, stop early with a protocol-aligned failure outcome only if the task allows it; otherwise do not guess results.
- 2) Input loading and schema sanity checks (before modeling)
- Discover and load the provided input artifacts (do not assume fixed paths; list the working directory and search by extension/names referenced in the task).
- Validate minimal required fields and shapes before computing:
- For MATPOWER-style data: confirm presence and consistent dimensions for bus, gen, branch, gencost, plus any reserve requirement fields if the task includes reserves.
- Build a bus-id to internal-index map if bus IDs are non-contiguous.
- Quick branch limit convention check (keep it lightweight):
- Identify which branch rating columns exist.
- If exactly one column is fully populated with positive limits for in-service branches, select it.
- Otherwise, select the most defensible column by a documented heuristic (highest fraction of positive finite values), and record the choice in metadata; do not run multi-scenario branches unless the task explicitly requests scenario output.
- 3) Compute required quantities using the chosen route (decision point: solver availability)
- If an optimizer is available (Route A):
- Formulate DC-OPF (and reserves if required by the task) matching the task description:
- Reference bus: choose deterministically (for example, smallest in-service bus id) and record it.
- Enforce generator bounds, power balance, and thermal limits for in-service branches using the selected limit column.
- If reserves are required: implement the reserve variables/constraints exactly as described by the task text (do not invent a reserve model).
- Solve with conservative iteration/time limits; record status, objective, and any infeasibility flags.
- If no optimizer is available (Route B):
- Only proceed if the environment provides an explicit alternative solving method (for example, a provided script/binary). Run it and capture outputs needed for the report.
- Otherwise, stop (do not fabricate dispatch/LMPs).
- 4) Assemble report data strictly from the task schema (no extra fields unless allowed)
- Build the JSON object to exactly match the discovered required schema:
- Include base vs counterfactual sections only if required.
- Include reserve results/prices only if required.
- Include branch binding identification only if required; use a single declared tolerance and store it in metadata if the schema allows.
- Ensure all numeric arrays have consistent lengths (for example, one entry per generator/bus/branch as required) and contain finite numbers.
- 5) Write and verify the output artifact (finalization gate; minimal stdout)
- Write the JSON to the exact required output path (execution anchor):
- Confirm the directory is writable before writing.
- Write atomically when possible (write temp file then rename) to avoid partial files.
- Reload-and-assert validation:
- Re-open the written file from the required path and `json.load` it.
- Assert required top-level keys exist and have correct types.
- Assert required nested keys exist; assert arrays have expected lengths derived from loaded inputs (not hard-coded constants).
- Assert required numeric fields are finite and within any task-stated ranges.
- Termination protocol:
- Unless the task explicitly allows narrative output, emit no extra prose beyond (at most) a single confirmation line that the file was created and validated.

## Constraints / Pitfalls
- Never spend unbounded time installing packages in restricted environments; do not attempt system-wide pip installs when blocked. Use a strict, small time budget for dependency handling and prefer fail-fast over long setup.
- Do not guess the report schema or output location: always extract required keys/path from the task text/tests, then validate by reloading and asserting structure at the exact verifier-visible path before finishing.