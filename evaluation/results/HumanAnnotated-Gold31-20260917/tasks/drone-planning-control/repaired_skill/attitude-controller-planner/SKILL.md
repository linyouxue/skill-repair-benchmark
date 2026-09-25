---
name: attitude-controller-planner
description: Use this skill when implementing the inner control loop for a quadrotor — attitude (roll/pitch/yaw) PID control and attitude planning (converting desired acceleration to desired Euler angles). For strict trajectory tracking, design the attitude loop quantitatively and keep it substantially faster than the outer position loop.
---

# Attitude Controller and Planner

## Overview

Two cooperating modules form the inner loop:

1. **Attitude planner** — converts desired linear acceleration to desired roll/pitch angles `(phi_des, theta_des)` while preserving desired yaw.
2. **Attitude controller** — PID feedback on Euler-angle/angular-rate errors to moments `[Mx, My, Mz]`.

The inner loop is not an independent cosmetic subsystem. For lateral flight, position acceleration is realized through roll/pitch; a slow attitude loop directly becomes position tracking error.

## Attitude Planner

Given desired acceleration `[ax, ay]` and yaw `psi`, compute desired roll/pitch using the small-angle inverse relation:

```text
phi_des   = (ax*sin(psi) - ay*cos(psi)) / g
theta_des = (ax*cos(psi) + ay*sin(psi)) / g
```

Return `rot = [phi_des, theta_des, psi]` and the desired angular-rate vector required by the interface. Preserve the planner/controller convention consistently throughout the simulation.

## Attitude Controller

1. `e = desired_rot - current_rot`
2. `integral_e += e * dt`
3. `M = I @ (kp * e + ki * integral_e + kd * (desired_omega - current_omega))`

Use `make_attitude_integral()` to create fresh integral state before each independent simulation candidate. Never reuse it across commands or candidate gain sets.

## Mandatory Bandwidth Separation

Because the controller multiplies the normalized PID acceleration by the inertia matrix, each attitude axis is approximately

```text
e_ddot + Kd_att * e_dot + Kp_att * e ≈ 0
```

for an initial gain design. Therefore choose

```text
Kp_att ≈ omega_att^2
Kd_att ≈ 2 * zeta_att * omega_att
```

with `zeta_att` around `0.8–1.1` as a stable starting region.

For cascaded position/attitude control, make the attitude loop materially faster than the position loop. A practical first design is

```text
omega_att ≈ 3–4 * omega_pos
```

subject to motor bandwidth, sampling rate, moment limits, and observed saturation. With a position bandwidth around `5–6 rad/s`, this naturally puts attitude proportional gains in the hundreds and derivative gains in the tens. Starting at a very slow attitude loop and searching only ±30% around it is usually insufficient for centimetre-scale lateral tracking.

These values are derived from the normalized closed-loop dynamics; they are not universal magic numbers. Recompute them when the plant or controller structure changes.

## Integral Action

- Keep attitude `Ki` small; excessive attitude integral causes wind-up and lateral oscillation.
- Do not use integral action to compensate for an under-damped or low-bandwidth P/D design.
- Reset the integral for every command and candidate.
- If actuator saturation occurs, clamp/disable integral accumulation while saturated or otherwise implement anti-windup.

## Strict-Tracking Tuning Procedure

1. Tune the attitude P/D loop first to achieve fast, well-damped tracking without motor saturation.
2. Verify roll/pitch tracking on the fastest lateral command, not only hover/takeoff.
3. Then tune the outer position loop.
4. If position tracking remains poor during lateral motion, inspect attitude error and motor saturation before raising position gains further.
5. Re-run the exact saved candidate from a clean state after tuning.

If the final acceptance criterion is a hard per-timestep position bound, the attitude loop must be judged by whether it enables that bound; “stable-looking attitude plots” are not sufficient.

## Critical Design Rules

- Never use mutable default integral state.
- `dt = 1.0 / params['sample_rate']`; do not hardcode it.
- Gains are element-wise `[phi, theta, psi]` gains before multiplication by `I`.
- Preserve sign conventions between desired acceleration, desired attitude, moment, and dynamics.
- Keep attitude bandwidth clearly above position bandwidth.
- Check motor saturation before interpreting a high-gain failure as “needs even more gain”.
- Do not accept a best-so-far gain set unless the downstream hard tracking constraints actually pass.

## Symptom-Based Tuning Guide

| Symptom | Action |
|---|---|
| Slow roll/pitch correction | Increase `omega_att` → raise matched `Kp_att` and `Kd_att` |
| Roll/pitch oscillation | Increase damping or reduce attitude bandwidth |
| Lateral position error grows while desired tilt is correct | Inspect attitude lag and motor saturation |
| Yaw drifts slowly | Add/increase small yaw integral only after P/D are stable |
| x/y oscillation in hover | Reduce attitude integral; verify damping and sign conventions |

## Integration in Main Loop

```python
att_integral = make_attitude_integral()

for iter_ in range(max_iter - 1):
    ...
    desired_state.rot, desired_state.omega = attitude_planner(desired_state, params)
    M = attitude_controller(current_state, desired_state, params, att_integral)
```



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

