# SKILL.md

## When to use
Use this skill when you must build a **drone simulation + planner + feedback controller** that executes multiple **natural-language motion commands** (takeoff/hover/land/point-to-point flight), producing **time-parameterized, piecewise-continuous desired trajectories** and **tuned PID gains** per command, and saving **evaluator-consumed artifacts** (JSON/NPY/plots) into a required results folder structure.

Before acting, gather/confirm:
- Where to read **system limits** (e.g., acceleration limits and any mass/inertia/thrust constraints) and the simulator timestep / horizon (`max_iter`).
- The exact **command grammar** and how to parse height/position/time from each file.
- The **required output formats**: exact JSON schemas, required NPY matrix shape and row layout, and required plot filenames.
- How success is judged: **per-timestep position error bound**, **overshoot**, **steady-state error**, and **trajectory acceleration-limit compliance**.

(From retrieved evidence: strict output schemas and object types are commonly graded; plotting/output objects must match requested labels/titles/filenames and be produced reliably.)

## Possible Failure Modes
- **Output schema drift**: wrong JSON keys, missing keys, extra nesting, wrong numeric types (e.g., ints/strings), wrong field names/case.
- **Wrong trajectory matrix layout**: mixing row/column orientation, using `(max_iter, 15)` instead of `(15, max_iter)`, or mis-ordering state components.
- **Inconsistent lengths**: planned vs actual trajectories saved with different `max_iter`, or controller running fewer steps than trajectory generation.
- **Acceleration limit violations**:
  - Planner produces discontinuous velocity/acceleration (spikes at segment boundaries).
  - Computing acceleration by finite differencing introduces peaks; forgetting to clip/smooth to respect limits at **every timestep**.
- **Per-timestep tracking failure**: only checking mean/RMS error instead of the strict “< bound at every timestep”.
- **Metric mismatch**: incorrect settling-threshold usage, wrong signal used for rise/settle/overshoot (e.g., using 3D norm vs axis), or computing metrics on planned rather than actual response.
- **PID tuning pitfalls**:
  - Gains tuned for one command reused for all commands.
  - Integral windup (especially for takeoff/landing) causing overshoot > allowed.
  - Derivative kick from setpoint steps; no filtering → noisy oscillations.
- **Command parsing errors**: mishandling parentheses/commas/spaces, units, negative coordinates, or swapping x/y/z.
- **Plot requirements missed**: missing directory, wrong filenames, unreadable plots, or plotting wrong signals.
- **Hardcoding from examples**: copying unrelated constants/paths/IDs from retrieved snippets rather than reading the current task’s files.

## Possible procedures
1. **Ingest constraints and simulation configuration**
   - Load system parameters (especially vertical/horizontal acceleration limits).
   - Determine timestep `dt` and `max_iter` (or infer from command duration and dt).
   - Decide coordinate/frame conventions for attitude (φ, θ, ψ) and angular rates (p, q, r) and use consistently in planner, controller, and logs.

2. **Parse each command into a canonical goal spec**
   - Implement a parser that maps command text into: `mode` (takeoff/hover/land/translate), start state assumptions, target position/height, and duration `T`.
   - Normalize into a common interface like `goal(t)` returning desired position/velocity/acceleration.

3. **Trajectory planning under acceleration limits**
   - Generate **piecewise-continuous** trajectories (position, velocity, acceleration) for the full horizon:
     - Prefer motion profiles that are naturally acceleration-bounded (e.g., trapezoidal/triangular velocity profiles, time-scaled polynomials with bounded derivatives).
     - Ensure continuity at segment boundaries (at least C1 for velocity; C2 if you want smoother acceleration).
   - Decision point: if naive polynomial violates accel limits, **time-scale** (increase segment duration) or **reduce peak velocity** to satisfy bounds.
   - Produce orientation/attitude references consistent with your control architecture:
     - If position controller outputs desired acceleration, convert it to desired roll/pitch (and yaw policy), respecting feasible tilt limits if modeled.
   - Populate the desired-state matrix rows exactly as required (pos/vel/orientation/angular vel/accel).

4. **Drone dynamics + motor model (simulation loop)**
   - Implement a forward simulation producing the “actual” state each timestep.
   - Keep the model stable and consistent (forces/torques → linear/angular acceleration → integrate).
   - Recovery check: if the simulation diverges (NaNs, unbounded values), add saturation on thrust/torque and reduce dt or gains.

5. **Cascaded PID control (position → attitude)**
   - Outer loop (position): track desired position/velocity and output desired acceleration (with integral and derivative terms as appropriate).
   - Inner loop (attitude): track desired φ, θ, ψ (and optionally p, q, r) and output torque commands.
   - Add practical protections:
     - **Anti-windup**: clamp integral state when actuators saturate or when error sign flips.
     - **Derivative filtering**: low-pass the derivative term or compute derivative on measurement to reduce kick.
     - **Saturation**: cap commanded acceleration/tilt to preserve feasibility and reduce overshoot.

6. **Per-command PID tuning loop**
   - For each command independently:
     - Choose a search strategy (coarse-to-fine grid, random search, coordinate descent).
     - Define a scalar objective that penalizes: max per-step position error, overshoot, steady-state error, and accel-limit violations (hard reject if any required constraint fails).
   - Decision point: if you cannot satisfy per-step error bound, prioritize stabilizing inner attitude loop first, then outer loop; reduce aggressiveness (kp/kd) to eliminate oscillations, then reintroduce integral carefully.

7. **Compute step-response metrics with the specified settling threshold**
   - Select the relevant response signal for the mode (e.g., altitude for takeoff/hover/land; position component or 3D distance for translation) and compute:
     - Rise time, settling time (using the provided threshold), overshoot percentage, steady-state error.
   - Keep metric computation consistent across commands and save in the exact schema.

8. **Write artifacts to the required folder structure**
   - For each command, create `/root/results/<cmd_id>/` and save:
     - `planned_trajectory.npy` and `actual_trajectory.npy` with shape `(15, max_iter)`.
     - `metrics_3d.json` and `tuning_results.json` matching the exact schemas.
     - `plots/` with required filenames.
   - Ensure plots clearly compare desired vs actual and include error curves used for constraint checks.

## Verification Checklist
- **Per-command outputs exist** in the correct directory structure; no missing files:
  - `metrics_3d.json`, `tuning_results.json`, `planned_trajectory.npy`, `actual_trajectory.npy`, and `plots/` with all required plot filenames.
- **JSON schemas match exactly**:
  - Correct keys, correct casing, numeric values are JSON numbers, `mode` is present.
  - PID gain arrays are length-3 float lists for each of the six gain fields.
- **NPY arrays are correct**:
  - Both planned and actual are `float` arrays with shape `(15, max_iter)`.
  - Row mapping matches the required layout (pos/vel/orientation/angular vel/accel).
  - Planned and actual share the same `max_iter` and timestep indexing.
- **Planner constraint compliance**:
  - At every timestep, planned accelerations respect vertical up/down and horizontal acceleration limits (check using the task’s definitions).
  - No large discontinuities at segment boundaries (inspect accel time series).
- **Controller success constraints** (for each command):
  - Per-timestep Euclidean position error is below the required bound **at every timestep** (verify max error, not just average).
  - `SteadyStateError` and `Overshoot_pct` satisfy thresholds.
- **Metrics computed with the specified settling threshold** and from the actual response (not the planned trajectory).
- **Plots reflect the saved trajectories** (desired vs actual overlays and error plots correspond to the same data arrays).
- **No contamination from retrieved examples**:
  - No copied IDs/paths/constants unrelated to the current task; all values derived from current command files and system parameters.
- **Safety/recovery check**:
  - Simulation produces finite values for all state elements; no NaNs/infs; if found, reduce gains/add saturation and re-run tuning.
