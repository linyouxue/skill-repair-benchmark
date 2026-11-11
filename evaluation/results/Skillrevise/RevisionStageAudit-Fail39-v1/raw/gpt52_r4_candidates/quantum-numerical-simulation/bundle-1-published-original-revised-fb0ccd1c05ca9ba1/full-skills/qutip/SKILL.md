# QuTiP Steady State + Phase Space Export (CSV) With Verifiable Checkpoints

## Purpose
Provide a reusable, environment-grounded procedure for generating steady-state quantum results (often open systems) and exporting derived 2D arrays (for example Wigner/phase-space grids) to CSV files, with strict post-write validation so completion claims are always backed by tool-visible evidence.

## When to Use
Use when a task requires producing one or more verifier-consumed artifacts (typically CSV matrices) from QuTiP/PIQS simulations, especially when computations may be heavy (steady-state solvers, large grids) and the environment may enforce time or resource limits.

## Procedure
- **1) Clarify the observable contract (before running anything).**
- Extract from the task: required output file names/paths, required matrix shape (if any), numeric type expectations, and the number of cases to run.
- If any of these are ambiguous, stop and ask or derive them from visible task files/tests (do not guess).
- Decide an output directory only from the task contract; otherwise discover a writable directory with a quick check (for example, list current directory and confirm write permissions).
- **2) Ground the environment and dependencies (discovery-first).**
- Confirm Python and QuTiP are importable in the current runtime by running a minimal import check.
- If the task mentions PIQS or optional modules, import-check those explicitly.
- If any import fails, take a bounded fallback: install the missing package only if the environment permits installs; otherwise report the missing dependency and stop (do not proceed with fake outputs).
- **3) Implement a two-phase execution plan to avoid timeouts.**
- Phase A (smoke test): run the full pipeline on a reduced workload (for example, smaller grid and/or fewer cases) to confirm:
- steady-state solver finishes,
- derived quantity computation runs end-to-end,
- CSV write + reload validation succeeds.
- Phase B (full run): only proceed if Phase A finishes within the available budget and resource usage appears stable.
- If Phase A already strains limits, do a bounded fallback:
- adjust solver options/tolerances conservatively,
- reduce intermediate storage (prefer expectation operators over storing full states when possible),
- and re-run only the smallest failing step to re-check feasibility.
- **4) Per-case loop with checkpoints (no irreversible claims without evidence).**
- For each required case:
- Build/parameterize the model using discovered task parameters (do not hard-code dimensions or rates unless they are specified invariants).
- Run the steady-state or time-evolution step.
- Checkpoint: record solver completion in tool output (return code, printed timing, or explicit "finished" message you emitted).
- Sanity checks (as applicable): object dimensions consistent, density matrix trace approximately 1, no NaNs/Infs.
- Compute the required 2D derived array (for example, Wigner on a grid).
- Checkpoint: assert the computed array shape matches the grid definition you are using for this phase.
- Write the CSV to the exact required output path for this case.
- Use atomic write semantics when possible (write to temp in same directory, then rename) to avoid partial files.
- **Post-write verification (must pass before continuing):**
- Existence/readability check at the exact path: run `ls -lh` or `stat` on the file and capture the output.
- Schema/shape check: reload the CSV (prefer a small Python snippet using numpy/pandas) and print/verify:
- it is numeric,
- it is 2D,
- its shape equals the required shape if specified (for example, exactly 1000x1000).
- If any check fails, stop and fix the smallest failing step; do not proceed to the next case.
- **5) Final verifier-aligned audit (before claiming completion).**
- Re-run the existence + reload/shape verification for all required outputs in one consolidated check.
- Only then report completion, and include the captured evidence (file listing and printed shapes) in the response.

## Constraints / Pitfalls
- **Never claim artifacts were generated or verified unless you include tool-visible evidence** (captured output of file existence and reload/shape checks). If the tool output is missing (timeouts, interrupted runs), treat the run as incomplete.
- **Do not jump directly to full-size heavy computations** (for example very large grids or many cases) without a smoke test and timing check; if the environment cannot complete the workload, apply a bounded fallback or report infeasibility with evidence rather than producing partial/guessed outputs.