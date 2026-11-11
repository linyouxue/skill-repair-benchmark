# Harness-Aligned Quadrotor Simulation, Control, And Artifact Delivery

## Purpose
Produce quadrotor simulation/controller outputs that pass an official repository harness by discovering the harness contract (paths, schemas, dynamics, metrics), implementing only what the harness evaluates, and enforcing verifier-parity gates (path-exact write/readback plus an official harness run) before declaring completion.

## When to Use
Use this skill when a task requires end-to-end quadrotor behavior (simulation + controller + any required logs/trajectory artifacts) and success is determined by an official test harness/verifier rather than by informal local checks.

## Procedure
- 1) Discover the official contract (no writing or tuning yet).
- Find the harness/verifier entrypoint by searching for: tests/ directories, grading scripts, Makefile targets, CI configs, and README instructions.
- Extract only observable requirements:
- Exact output paths and filenames the harness reads (absolute paths are allowed if explicitly required by the task/harness).
- Output formats and schemas (array shapes, required keys, file types).
- Simulation and controller IO: state representation (Euler vs quaternion), units, coordinate frame conventions, dt, horizon length, and any required initial conditions.
- Scoring/fail conditions (thresholds, settling definitions, termination conditions) as implemented in the harness.
- Decision: If any of the above is ambiguous, inspect the harness code that loads outputs and computes metrics; do not guess.
- 2) Ground your implementation to the repository model before changing algorithms.
- Identify the authoritative dynamics and actuator models used for evaluation (motor/thrust model, gravity, integration method, saturation rules).
- Align state update math to the harness model:
- Use the same state variables and kinematics mapping the harness uses (do not substitute simplified updates unless the harness does).
- Use dt and indexing exactly as the harness expects (including off-by-one conventions for control vs state timestamps).
- Checkpoint: Run the smallest available harness scenario (or unit test) that exercises loading and one-step simulation; confirm it executes and that your code is being called.
- 3) Implement/tune controller and planner only within the harness-evaluated interface.
- Implement the required controller inputs/outputs exactly (command type, shape, ordering, units).
- Add a bounded tuning loop driven by harness-observed metrics:
- Change one of: gains, time-scaling, or smoothing per iteration.
- Stop after one controlled fallback if a hard constraint is violated (thrust/rate/saturation) and escalate to a method-level change (for example, different trajectory time allocation or using the repository-provided controller template) instead of endless retuning.
- Checkpoint: Log and report the first failing timestep and signal channel according to the harness metric (not a custom metric).
- 4) Write outputs only where the harness reads them, then verify in place (path-exact gate).
- Write artifacts ONLY to task/harness-specified output paths and filenames (including explicit absolute paths when provided by the contract).
- Execution anchor (must do before running harness):
- List/stat the exact output paths.
- Reload the artifacts using the same loader code path the harness uses (import/call it if available); assert schema/shape/key requirements found in Step 1.
- Decision: If write fails due to permissions/mounts, diagnose the harness-required output root (mount points, writable directories) and fix the environment; do not silently redirect outputs to a different location.
- 5) Run the official harness/verifier as the final gate (not optional).
- Execution anchor:
- Execute the discovered harness entrypoint exactly as intended (script/command/target).
- Capture exit code and stdout/stderr; identify the precise failing assertion or metric component if it fails.
- If the harness fails:
- Classify the failure as one of: path/load error, schema mismatch, dt/indexing mismatch, dynamics mismatch, controller performance/constraints.
- Apply one bounded fix that directly targets the failing class, then rerun the harness.
- If the same class persists after the bounded fix, escalate to a method-level repair (swap to repository reference dynamics/controller interface, or replicate harness integration/metric code rather than approximating it).

## Constraints / Pitfalls
- Do not treat local plots, limit scans, or custom error scripts as acceptance. The only completion criterion is a passing official harness/verifier run plus in-place readback of artifacts at the exact harness-consumed paths.
- Do not ban absolute paths. Follow the explicit task/harness contract (even if it specifies /root/...); only avoid hard-coded paths when the contract does not specify them, in which case you must discover them from the harness loader logic.