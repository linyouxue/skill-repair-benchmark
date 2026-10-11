---
name: motor-model-dynamics
description: Use this skill when simulating quadrotor physical dynamics — mapping desired thrust/moments to motor RPMs, applying first-order motor lag, and integrating the nonlinear equations of motion. Under strict per-timestep tracking constraints, use a high-order integrator and validate timestep sensitivity; forward Euler is not an acceptable final integrator.
---

# Motor Model and Dynamics Simulation

## Overview

Two modules form the physics layer:

1. **Motor model** — maps desired `[F, Mx, My, Mz]` to desired motor RPM, applies motor lag, and produces actual force/moment.
2. **Dynamics** — evaluates the nonlinear 16-state equations of motion and integrates them over each control interval.

For a tight maximum position-error criterion, numerical integration accuracy is part of correctness. Do not tune a controller against one integration scheme and then assume a lower-order final simulator is equivalent.

## Motor Model

For an X-frame quadrotor with arm length `d`, thrust coefficient `cT`, and torque coefficient `cQ`, use the allocation matrix

```text
         motor:  1      2      3      4
Thrust:         +cT    +cT    +cT    +cT
Roll  (Mx):      0    +d*cT    0    -d*cT
Pitch (My):    -d*cT    0    +d*cT    0
Yaw   (Mz):    -cQ    +cQ    -cQ    +cQ
```

Implementation:

1. Solve `prop_matrix @ rpm_sq = [F, Mx, My, Mz]`.
2. Clamp negative `rpm_sq` to zero before square root.
3. Clip desired motor speeds to configured RPM limits.
4. Apply first-order lag: `rpm_dot = motor_constant * (rpm_desired - rpm_current)`.
5. Compute actual force/moment from the current motor RPM through the same allocation matrix.

Keep desired and actual motor quantities separate. Do not apply the desired force/moment directly to the rigid body while also claiming to model motor lag.

## Dynamics State

The 16-element state is:

| Indices | Meaning |
|---|---|
| 0:3 | position `[x, y, z]` |
| 3:6 | velocity `[vx, vy, vz]` |
| 6:9 | Euler angles `[phi, theta, psi]` |
| 9:12 | angular velocity `[p, q, r]` |
| 12:16 | motor RPM `[w1, w2, w3, w4]` |

Compute derivatives using the nonlinear thrust projection, gravity, rotational dynamics, and motor-lag derivative. Read `mass`, `gravity`, `inertia`, `sample_rate`, RPM limits, and motor constants from the system parameter file.

## High-Order Integration Is a Hard Requirement for Strict Tracking

The baseline implementation should integrate each control interval with `scipy.integrate.solve_ivp(..., method='RK45')`, holding the command force/moment and motor-rate input constant over that interval.

A fixed-step classical RK4 implementation is also acceptable when performance matters, provided it integrates the **full coupled state** consistently over the control interval.

**Do not use first-order forward Euler as the final result generator when the task has a hard per-timestep centimetre-scale tracking threshold.** Euler error can be of the same order as the allowed tracking margin and can mislead the gain search.

For fixed-step RK4:

```python
def rk4_step(state, dt, f):
    k1 = f(state)
    k2 = f(state + 0.5 * dt * k1)
    k3 = f(state + 0.5 * dt * k2)
    k4 = f(state + dt * k3)
    return state + (dt / 6.0) * (k1 + 2*k2 + 2*k3 + k4)
```

The derivative function must cover position, velocity, attitude, angular rate, and motor RPM state under the same held control input.

## Timestep Sensitivity Check

Before freezing a controller under a hard tracking bound, verify the numerical result is not an integration artifact:

1. Run the candidate with the intended control timestep `dt = 1/sample_rate` using RK45 or RK4.
2. On at least the most demanding command, repeat with an integration substep of `dt/2` (while holding controller updates at the original control rate if appropriate).
3. Compare position trajectories and the maximum tracking error.
4. If the change is material relative to the acceptance margin, refine integration before tuning further.

This check distinguishes control-design failure from numerical-discretization failure.

## Motor and Actuator Limits

Use configured RPM limits. Derived thrust capability is:

```text
T_max = 4 * cT * rpm_max^2
T_min = 4 * cT * rpm_min^2
```

Monitor saturation during tuning. If motors spend significant time clipped, simply raising PID gains cannot improve faithful tracking and may increase overshoot/wind-up.

## Initial-State and Reproducibility Rules

- Use one explicit, consistent initial-state convention for all tuning candidates.
- Do not carry state, motor RPM, or controller integral from one command/candidate into the next.
- Do not change the initial-state convention merely to make a failing candidate appear better.
- The gains written to the final tuning artifact must regenerate the final trajectories when the same simulator and initial state are rerun.

## Critical Design Rules

- Read `dt` from `sample_rate`; never hardcode it.
- Apply motor lag before using actual motor force/moment in rigid-body dynamics.
- Integrate the full coupled state with RK45 or RK4 for final outputs.
- **Forward Euler is diagnostic-only, not a final strict-tracking integrator.**
- Reset simulator state for each command and each gain candidate.
- Check actuator saturation and numerical sensitivity before blaming PID gains.
- Re-run the selected final gains from a clean state and save only that final simulation's trajectories.



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

