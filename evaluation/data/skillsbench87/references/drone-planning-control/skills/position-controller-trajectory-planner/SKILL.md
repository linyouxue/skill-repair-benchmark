---
name: position-controller-trajectory-planner
description: Use this skill when implementing the outer control loop for a quadrotor — position PID control (position/velocity error → thrust and desired acceleration) and trajectory planning from flight-plan waypoints (takeoff, hover, fly, land segments → smooth 15-row state matrix). For strict tracking tasks, use quantitative bandwidth design and a blocking per-command acceptance loop rather than a small local gain sweep.
---

# Position Controller and Trajectory Planner

## Overview

Two cooperating modules form the outer loop:

1. **Trajectory planner** — converts waypoints + modes into a `(15 × max_iter)` desired state matrix using the specified smooth interpolation per segment.
2. **Position controller** — PID feedback on position/velocity errors → thrust `F` and desired acceleration.

For tasks with a hard per-timestep tracking bound, producing all required files is not completion. The controller must be tuned until the saved trajectories themselves pass every hard dynamic constraint.

## Trajectory Planner

### Segment modes

| Mode | Behaviour |
|---|---|
| `'hover'` | Constant position, zero velocity and acceleration |
| `'takeoff'` | Smooth spline from ground to target height |
| `'fly'` | Smooth spline from start position to end position |
| `'land'` | Smooth spline from current height to ground |

### WaypointTrajectory — implementation logic

Build a callable object that steps through a clamped cubic spline one sample at a time:

- In `__init__`, fit `CubicSpline` over waypoint positions versus arrival times with zero first derivative at the two endpoints (`bc_type=((1, 0), (1, 0))` per dimension), store `dt = 1/sample_rate`, and initialise `t_current` to the first waypoint time.
- On each `__call__`, evaluate position, first derivative for velocity, and second derivative for acceleration; advance `t_current` by `dt`; return the values needed by the 15-row state matrix.
- For non-hover segments, interpolate yaw separately over the same segment.
- For hover, write the requested constant position directly and keep velocity/acceleration zero.

**Do not silently replace a specified trajectory family with a different one merely because the endpoints match.** A downstream simulation or reproducibility check may regenerate the planned trajectory from the same waypoints. If you intentionally change interpolation, prove that the saved trajectory remains compatible with the expected planner before accepting it.

### `trajectory_planner` signature

```python
def trajectory_planner(waypoints, max_iter, waypoint_times, sample_rate, modes):
    # Returns (15 x max_iter) trajectory_state
    # rows 0:3  pos, 3:6 vel, 6:9 orientation, 9:12 ang_vel, 12:15 acc
```

## Position Controller

### Implementation logic

PID control on position and velocity errors:

1. `pos_err = current_pos - desired_pos`
2. `vel_err = current_vel - desired_vel`
3. `integral_e += pos_err * dt`
4. `acc = desired_acc - kp * pos_err - ki * integral_e - kd * vel_err`
5. `F = mass * (gravity + acc[2])`
6. Return `(F, acc)`.

Use `make_position_integral()` to create a fresh `{"e": zeros(3)}` dict before **every independent simulation candidate**. Never reuse integral state between commands or tuning candidates.

## Quantitative Gain Design for Strict Tracking

When the acceptance criterion contains a small hard maximum tracking error, do **not** begin with toy gains such as `kp≈0.1` and then search only a narrow neighbourhood. Derive a useful starting region from the closed-loop dynamics.

Ignoring inner-loop lag for a first design pass, the position error approximately obeys

```text
e_ddot + Kd * e_dot + Kp * e ≈ 0
```

so for each axis choose a target natural frequency `omega_pos` and damping ratio `zeta_pos` and start from

```text
Kp ≈ omega_pos^2
Kd ≈ 2 * zeta_pos * omega_pos
```

For a fast sampled quadrotor with a strict centimetre-scale tracking bound, a useful first search region is typically:

- `omega_pos`: about `4–7 rad/s`
- `zeta_pos`: about `0.8–1.1`
- therefore `Kp` is commonly in the tens, not near zero
- `Kd` is commonly in the high single digits to low teens
- keep `Ki` small initially; add only enough integral action to remove persistent bias

Treat these as **physics-derived starting ranges, not universal constants**. Recompute/expand them if the motor time constant, sample rate, mass, trajectory acceleration, or observed saturation indicate a different bandwidth is needed. The z axis may require a somewhat higher position bandwidth than x/y when thrust/motor lag dominates altitude tracking.

The attitude loop must be faster than the position loop; use the attitude-controller skill to maintain clear bandwidth separation. Raising position gains while leaving a slow attitude loop usually worsens lateral tracking rather than fixing it.

## Tuning Search Must Be Constraint-Driven

For each command, tune gains against the **actual acceptance constraints**, not only a smooth score.

1. Start from bandwidth-derived gains, not from a near-zero controller.
2. Evaluate the full simulation from a clean initial state.
3. Compute the exact hard metrics from the generated arrays.
4. If a candidate fails, classify the failure before changing gains:
   - large transient/max position error with stable motion → increase closed-loop bandwidth;
   - oscillation/overshoot → increase damping or reduce proportional gain;
   - persistent final bias → add small integral action;
   - lateral error while attitude lags → speed up/damp the attitude loop first;
   - motor saturation → reduce requested trajectory aggressiveness where allowed or back off gains; do not keep increasing gains blindly.
5. If a local multiplicative grid around the current gains contains no passing candidate, **expand the search range**. A `0.7/1.0/1.3` sweep around a failing low-gain baseline is only a diagnostic step, not a valid stopping condition.

Optimize hard feasibility first. A candidate with the best score but `max_position_error >= limit` is still a failure.

## Mandatory Per-Command Acceptance Gate

Before accepting a command, recompute these quantities from the **exact arrays that will be saved**:

```python
pos_err = np.linalg.norm(actual[0:3] - planned[0:3], axis=0)
max_position_error = float(np.max(pos_err))
steady_state_error = float(np.linalg.norm(actual[0:3, -1] - planned[0:3, -1]))

az = planned[14]
horiz_acc = np.sqrt(planned[12]**2 + planned[13]**2)
accel_ok = (
    np.all(az <= accel_limit_up)
    and np.all(az >= -accel_limit_down)
    and np.all(horiz_acc <= accel_limit_horiz)
)
```

Also compute the required overshoot metric using the task's specified settling threshold.

The candidate passes only if **every** required strict inequality passes. In a task using 5 cm and 5% bounds, for example, the logic is equivalent to:

```python
passed = (
    steady_state_error < 0.05
    and overshoot_pct < 5.0
    and max_position_error < 0.05
    and accel_ok
)
```

If `passed` is false, do not write “complete” or freeze that candidate as final merely because it is currently best.

## Reproducibility Contract for Saved Gains and Trajectories

`tuning_results.json`, `planned_trajectory.npy`, and `actual_trajectory.npy` must describe the **same simulation candidate**.

- After selecting gains, rerun the simulator with exactly those gains and a fresh state/integral state.
- Save the arrays from that rerun, not arrays left over from an earlier candidate.
- Reload the saved gains and regenerate once; compare against the saved trajectories before final acceptance.
- Do not report one candidate's gains with another candidate's trajectories.

This prevents a tuning loop from accidentally producing internally inconsistent artifacts.

## Mandatory Final All-Command Sweep

After all per-command folders exist, perform a fresh final sweep over every command. Read each final artifact back from disk and recompute the hard constraints. Maintain an explicit `failed_commands` list.

```python
failed_commands = []
for label in command_labels:
    # reload final JSON/NPY files
    # recompute every hard criterion
    if not command_passes:
        failed_commands.append(label)

assert not failed_commands, f"still failing: {failed_commands}"
```

**A non-empty failure list blocks completion.** File/schema completeness, successful plotting, or “all modes have at least one success” are useful checks but are not substitutes for the all-command dynamic gate when the task requires every command to succeed.

## Required Output File Locations

For each command file (e.g. `001.txt`), create a dedicated output directory and write all outputs there:

```text
/root/results/
  001/
    planned_trajectory.npy
    actual_trajectory.npy
    metrics_3d.json
    tuning_results.json
    plots/
      desired_vs_actual.png
      errors.png
      cumulative_errors.png
```

Save the planned trajectory immediately after planning and the actual trajectory from the final accepted simulation candidate.

## Physical Acceleration Limits

Read limits from `system_params.yaml`; never hardcode them. For each timestep:

- upward: `az <= accel_limit_up`
- downward: `az >= -accel_limit_down`
- horizontal: `sqrt(ax**2 + ay**2) <= accel_limit_horiz`

If the planner violates these bounds, fix the planned trajectory first. PID tuning cannot make an infeasible desired acceleration physically achievable.

## Critical Design Rules

- Never use a mutable default for PID integral state.
- Reset integral state for every command and every tuning candidate.
- `dt = 1.0 / params['sample_rate']`; never hardcode the timestep.
- `time_final = waypoint_times[-1]`; derive it from the parsed flight plan.
- Keep the documented `(15 × max_iter)` row layout exact.
- Preserve the specified trajectory interpolation unless you validate compatibility.
- Use quantitative closed-loop bandwidth design before brute-force search.
- **Best-so-far is not pass.** Hard feasibility gates decide acceptance.
- End only after the final all-command sweep reports zero failures.

## Symptom-Based Tuning Guide

| Symptom | Primary action |
|---|---|
| Slow position tracking, no oscillation | Increase position-loop natural frequency (`Kp`, with matched `Kd`) |
| Position overshoot/oscillation | Increase damping (`Kd`) or reduce bandwidth |
| Persistent altitude offset | Add a small `Ki_pos[2]` after P/D are stable |
| Lateral tracking lags while roll/pitch lag | Increase attitude-loop bandwidth/damping first |
| x/y oscillation during hover | Reduce integral action; verify attitude damping |
| Motor RPM repeatedly saturates | Back off gains or reduce trajectory aggressiveness; do not integrate wind-up |



## Mandatory Execution / Completion Contract

For implementation tasks, analysis is not completion. Keep using the available tools until the requested artifacts have actually been created and checked.

- Do not end after listing files, reading parameters, proposing code, or describing the next command.
- When you intend to run a command, invoke the execution tool. Do not print a JSON-shaped tool request, shell command, or “I’ll do X next” as ordinary assistant text and then stop.
- A shell syntax error is an unfinished intermediate state. Correct the command and continue immediately.
- Before any final answer, verify that the required output root exists, every expected per-item directory exists, and the final acceptance sweep has zero failures.
- For batch simulation tasks, a missing `/root/results`, a missing command folder, or any non-empty `failed_commands` list means the task is not finished.
- Prefer writing one reusable driver script and executing it over repeatedly narrating small manual steps.

Completion is an observable state on disk plus successful checks, not an intention to perform the next operation.



## Mandatory Benchmark Plant / Controller Contract

For this simulation task, the equations documented in the loaded Skills are the implementation contract. Do not replace them with a different, more physically complete quadrotor model merely because it appears more realistic. Reproducibility against an independently regenerated trajectory is part of correctness.

### Position-controller contract

Use the documented controller literally:

```python
pos_err = current_pos - desired_pos
vel_err = current_vel - desired_vel
integral_e += pos_err * dt
acc = desired_acc - kp * pos_err - ki * integral_e - kd * vel_err
F = mass * (gravity + acc[2])
```

`F` is the scalar z-thrust expression above. Do **not** silently replace it with `mass * norm(acc + [0,0,g])` or tilt-compensated thrust unless the task explicitly changes the plant contract.

### Attitude-planner contract

Use the Skill's small-angle inverse mapping exactly:

```python
phi_des   = (ax*sin(psi) - ay*cos(psi)) / g
theta_des = (ax*cos(psi) + ay*sin(psi)) / g
rot_des = [phi_des, theta_des, psi]
```

Do not substitute a geometric rotation-matrix construction or a normalized thrust-vector attitude planner for this task. A mathematically reasonable alternative is still a different simulator contract.

### Motor allocation contract

Use exactly the documented 4x4 allocation matrix:

```text
[[ cT,     cT,     cT,     cT],
 [  0,   d*cT,      0,  -d*cT],
 [-d*cT,   0,     d*cT,     0],
 [-cQ,     cQ,    -cQ,     cQ]]
```

Do not reconstruct a different matrix from motor-spread angles or another frame geometry. The configured parameter file may contain additional physical fields that are not part of this benchmark's documented equations; unused parameters are not permission to redefine the plant.

### Dynamics contract

Use the state equations described by the Skill, including these conventions:

- position derivative = current velocity;
- translational acceleration uses the documented ZYX thrust projection and gravity expressions;
- Euler-angle derivative = `state[9:12]` under this task's simplified convention;
- angular-velocity derivative = `solve(I, M)`;
- motor derivative = `motor_constant * (rpm_desired - rpm_current)`.

Do not add body-rate/Euler-rate transforms, gyroscopic `omega x (I omega)` terms, or other omitted rigid-body terms in the final benchmark simulator. Such additions change the generated trajectory and invalidate gain/trajectory reproducibility.

### Initial state

Start each independent simulation from the task's direct waypoint/state convention and a fresh zero-initialized 16-state vector, then set only the explicitly required initial position/yaw components. Do not silently pre-equilibrate hidden state such as motor RPM to hover speed unless the documented task contract instructs you to do so.

### Reproducibility gate

Before tuning 30 commands, first implement one canonical simulator from these exact equations. Then:

1. Run a representative command from a fresh state twice with the same gains and assert trajectory equality within numerical tolerance.
2. Use this same simulator for tuning, final generation, and the arrays saved to disk.
3. Do not tune against one model and save results from another.
4. Keep the existing all-command hard acceptance gate. A candidate is complete only when the exact contract implementation produces passing final artifacts.

When a previous attempt used a more realistic alternative model, replace it rather than trying to compensate for the model mismatch by retuning gains.

