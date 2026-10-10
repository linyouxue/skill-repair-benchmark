# Quadrotor End-to-End Simulation And Reporting (Trajectory, Control, Metrics, Outputs)

## Purpose
Produce verifier-consumable quadrotor simulation results by discovering the repo contract first, then running an end-to-end loop: command ingestion, trajectory generation with acceleration limits, closed-loop control, physics integration, metrics/plots generation, and strict output grounding plus schema checks.

## When to Use
Use this skill when the task requires end-to-end deliverables (per-command runs, tuned control behavior, metrics/plots/files written for a verifier) and the repo/environment constraints are unknown or variable, so you must discover entrypoints, required output paths, and artifact schemas before implementing or running.

## Procedure
- 1) Discover the contract before coding or running
- Locate any authoritative sources in the environment: repo README/specs, tests, verifier scripts, example outputs, or config files.
- Extract and record (do not guess) the following, leaving unknown if not found:
- Input command formats and where they live (file patterns, folders).
- Required output root path(s) and per-run directory conventions.
- Required artifact list (filenames, extensions) and any schema hints (required keys/columns).
- Timebase requirements (dt, sample_rate, horizon) and numeric requirements (e.g., settling_threshold = 0.02 if present).
- Decision point: if no contract is discoverable, stop and implement a minimal, clearly logged default output bundle, but keep outputs organized and easy to map to a future contract (one folder per command/run).
- 2) Validate inputs and assumptions (fail fast, no irreversible writes)
- Confirm required input files exist and are readable; if multiple candidates exist, list them and select deterministically (e.g., newest by mtime) while logging the choice.
- Validate parameter sources (system params, vehicle params) by checking required fields exist before use (mass, gravity, inertia representation, motor limits if present).
- Decision point: if critical fields are missing, fall back to a simplified model only if it still allows producing required artifacts; otherwise halt and report the missing fields.
- 3) Build an end-to-end pipeline skeleton with stable interfaces
- Define explicit interfaces (function signatures or module boundaries) for:
- parse_commands() -> list of command specs
- generate_reference(command, limits) -> time series reference (pos/vel/acc or attitude/thrust)
- controller_step(state, reference, gains) -> actuator commands (thrust/moments or motor targets)
- plant_step(state, actuators, dt, params) -> next state
- compute_metrics(run_data, thresholds) -> dict/table
- write_outputs(run_id, artifacts) -> files
- Constraint: keep state definitions and units consistent and documented in-code (no silent unit mixing).
- 4) Trajectory generation with explicit acceleration-limit enforcement
- Generate a time-parameterized reference for each command.
- Enforce acceleration limits with an explicit check:
- Compute commanded/reference acceleration over the timebase and assert it does not exceed configured limits (or log violations and apply smoothing/time-scaling).
- Decision point: if the reference violates limits, apply the smallest change that restores feasibility (time scaling or jerk/accel limiting), then re-check.
- 5) Closed-loop simulation with environment-grounded integrator choice
- Choose integration method based on available tools:
- Prefer fixed-step integrators (Euler or RK2/RK4) with dt derived from discovered sample_rate/dt.
- Use advanced integrators only if the dependency is present and verified usable.
- Motor/actuator mapping:
- Discover vehicle geometry and motor ordering/sign conventions from params/config if available.
- If geometry is unknown, use a generic allocation fallback (e.g., pseudoinverse mapping) and add a validation check that resulting actuator commands are finite and within limits.
- Control:
- Implement cascaded control only if required by the contract; otherwise keep a minimal stable controller.
- Tuning rule: tune per command only within bounded iterations (e.g., N trials), and always keep a safe default gain set as fallback.
- Execution checkpoint per run:
- Log: timebase, integrator, saturation events, max accel observed, and whether any NaNs/Infs occurred.
- If NaN/Inf appears: stop the run, lower dt or clamp/saturate, and rerun once (bounded fallback).
- 6) Ground outputs in verifier-visible paths and validate schemas (hard gate)
- Write artifacts only to the exact discovered output root(s); create directories only under that root.
- Required artifacts (discover-driven):
- Metrics file(s) (json/csv) and plot/image files if required.
- Any trajectory/state logs required by the contract.
- Post-write grounding check:
- For every required artifact path: assert it exists, is readable, and non-empty.
- Post-write schema check (reload what you wrote):
- JSON: parse and assert required keys exist and types are correct.
- CSV: load and assert required columns exist and row count matches timebase.
- Numeric arrays: assert expected shape consistency with the run length.
- Numeric sanity: all finite; no silent NaNs; thresholds (like settling_threshold = 0.02) applied only if explicitly required/discovered.
- Decision point: if any artifact fails existence or schema checks, fix locally (path/schema) and re-run only the write+validation step (not the whole simulation) when possible.
- 7) Bounded fallback handling for common tool/environment failures
- Plotting fails (backend/missing fonts): fall back to saving minimal plots (no latex, no tight layout), or skip plots only if the contract does not require them; always keep metrics/logs.
- Missing heavy dependencies (e.g., scipy): switch to fixed-step integration and numpy-only computations; re-run the smallest validation checkpoint (finite state, output existence).
- Ambiguous requirements: generate both a minimal and an extended artifact set (within the same output root) only if it does not violate the contract; otherwise pause for clarification.

## Constraints / Pitfalls
- Do not hard-code output paths, motor ordering, geometry signs, dt, or integrator choices; discover them from repo/task artifacts first, and validate with explicit checks before committing to a run.
- Do not claim completion unless the final grounding + reload-based schema validations pass on the exact verifier-visible output paths; if a required contract element is unknown, record it as unknown and avoid inventing hidden requirements.