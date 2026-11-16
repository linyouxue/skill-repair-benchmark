---
name: attitude-controller-planner
description: Use this skill when implementing the inner control loop for a quadrotor — attitude (roll/pitch/yaw) PID control and attitude planning (converting desired acceleration to desired Euler angles). Covers gain layout, integral reset pattern, and the attitude planner inverse kinematics.
---

# Attitude Controller and Planner

## Overview

Two cooperating modules form the inner loop:

1. **Attitude planner** — converts desired linear acceleration → desired roll/pitch angles (φ_des, θ_des)
2. **Attitude controller** — PID feedback on Euler angle errors → moments [M₁, M₂, M₃]

## Attitude Planner

### Implementation Logic (frames + unambiguous mapping)

**Frame conventions (assumed throughout):**
- World/inertial frame **W**: x-forward, y-left, z-up.
- Body frame **B**: x-forward, y-left, z-up (thrust along +z_body).
- Gravity in world: `g_vec = [0, 0, -g]` with `g = 9.81`.
- Desired linear acceleration `a_des = [ax, ay, az]` is expressed in **world**.
- Yaw `ψ` is world heading (rotation about +z_world). Roll `φ` about +x_body, pitch `θ` about +y_body.

#### Full (robust) mapping via desired thrust direction
1. Form the desired total acceleration including gravity compensation:
   - `a_total = a_des - g_vec = [ax, ay, az + g]`
2. Desired body z-axis in world:
   - `b3_des = a_total / ||a_total||`  (if `||a_total||` is very small, fall back to `[0,0,1]`)
3. Set desired yaw by defining a world-frame heading direction:
   - `b1_yaw = [cos(ψ_des), sin(ψ_des), 0]`
4. Construct remaining axes:
   - `b2_des = normalize(cross(b3_des, b1_yaw))`
   - `b1_des = cross(b2_des, b3_des)`
5. Convert the rotation matrix `R_des = [b1_des b2_des b3_des]` to Euler angles `(φ_des, θ_des, ψ_des)` using your project’s Euler convention.

This avoids small-angle sign mistakes and works for larger tilts.

#### Small-angle horizontal approximation (only if tilts are small)
When `|φ|,|θ|` are small and `az` is near 0, you can approximate using the yaw-rotated horizontal acceleration:
- Rotate desired horizontal accel into a “yaw-aligned” frame:
  - `a_x' =  ax*cos(ψ) + ay*sin(ψ)`
  - `a_y' = -ax*sin(ψ) + ay*cos(ψ)`
- Then (with +z up and thrust +z_body):
  - `θ_des ≈  a_x' / g`
  - `φ_des ≈ -a_y' / g`

#### Yaw and yaw-rate outputs
- Return `rot_des = [φ_des, θ_des, ψ_des]`.
- If a desired yaw rate `r_des` is provided, return `omega_des = [0, 0, r_des]`.
- If no yaw-rate is planned, set `r_des = 0` and let the attitude controller track `ψ_des` (with angle wrapping).

## Attitude Controller

### Implementation Logic (yaw wrapping, body-rate D-term, saturation, anti-windup)

Attitude control should be implemented in a way that **does not** differentiate Euler angles and **does** handle yaw discontinuities.

1. **Angle error (with yaw wrapping):**
   - `e = desired_rot - current_rot`
   - Wrap yaw error into `[-π, π]`:
     - `e[2] = wrap_to_pi(e[2])`

2. **Derivative term source:**
   - Use **measured body rates** `ω = [p, q, r]` from the state (gyroscope / simulator), not finite-differenced Euler angles.
   - Use the planned desired body rates `ω_des` (often `[0,0,r_des]`).
   - Rate error: `e_ω = ω_des - ω`

3. **Integral update + anti-windup (clamp or conditional integration):**
   - Candidate integral: `integral_e += e * dt`
   - Clamp per-axis: `integral_e = clip(integral_e, -i_lim, +i_lim)`
   - Recommended: integrate only when the corresponding moment is **not** saturated (see step 5), or back-calculate.

4. **Compute raw moments (element-wise gains, then inertia scaling):**
   - `u = kp * e + ki * integral_e + kd * e_ω`
   - `M_raw = I @ u`
   Notes:
   - `kp,ki,kd` are vectors `[φ, θ, ψ]` applied element-wise.
   - `I` is the 3×3 inertia matrix in body coordinates.

5. **Saturation (required for stability in worst-case commands):**
   - Angle command saturation at the planner output:
     - `|φ_des| ≤ φ_max`, `|θ_des| ≤ θ_max` (typical 20–35°; pick per platform)
   - Moment saturation in controller:
     - `M = clip(M_raw, -M_max, +M_max)` (per-axis)

6. **Integral reset pattern:**
   - Reset or decay integrator when switching modes (takeoff/hover/land/fly) or when commanded attitude changes abruptly.

Use `make_attitude_integral()` to create a fresh `{"e": zeros(3)}` dict before the simulation loop. Never use a mutable default argument for this state.

## Gain Tuning (starter ranges + procedure)

These gains are **platform-dependent**, but you should start from a conservative, stable set and tune to meet **per-timestep error < 0.05 m** (which requires very tight attitude tracking).

### Recommended starter ranges (simulation, normalized moments)
- Start with `ki_att = [0, 0, 0]` until P/D are stable.
- Typical starting points:
  - `kp_att`: roll/pitch larger than yaw, e.g. `[80..200, 80..200, 30..120]`
  - `kd_att`: add damping using body-rate error, e.g. `[5..40, 5..40, 1..20]`
  - `ki_att`: small, e.g. `[0..1.0, 0..1.0, 0..0.5]` with strict integral clamping

### Practical tuning procedure (inner-loop first)
1. **Freeze outer loop** (or command a small fixed tilt / yaw step). Tune attitude only.
2. Increase `kp_att[0:2]` until roll/pitch are fast but not oscillatory.
3. Increase `kd_att[0:2]` until overshoot is minimal and oscillations are critically damped.
4. Tune yaw similarly (`kp_att[2]`, then `kd_att[2]`), ensuring yaw error is wrapped to `[-π,π]`.
5. Add small `ki_att` only to remove steady bias; clamp integrator and verify no oscillation.
6. Re-enable the position controller and retune outer-loop gains if needed (but do **not** compensate for a weak attitude loop by inflating position gains).

## Critical Design Rules

- **Statefulness:** Never use a mutable default for the integral — this causes wind-up across simulation runs. Always pass `integral` explicitly and create it with `make_attitude_integral()` before the loop.
- **Yaw wrapping (mandatory):** Always compute yaw error with angle wrapping: `wrap_to_pi(ψ_des - ψ)`; otherwise you will command large, wrong-way yaw steps at ±π.
- **Derivative term source:** Do **not** finite-difference Euler angles for D; use measured body rates `[p,q,r]` (and desired `[p_des,q_des,r_des]`). Euler-angle differentiation is noisy and frame-coupled.
- **Saturation + anti-windup:**
  - Saturate desired angles: `φ_des, θ_des` to safe bounds.
  - Saturate moments `M` to actuator limits.
  - Clamp the integrator (`i_lim`) and/or freeze integration while saturated (or use back-calculation). This is required to prevent overshoot and oscillation.
- **Gravity/sign consistency:** Ensure your accel→attitude mapping matches your world/body conventions (+z up, thrust +z_body, `g_vec=[0,0,-g]`). If you change conventions, change the planner formulas accordingly.
- **Time step:** `dt = 1.0 / params['sample_rate']` — never hardcode `0.005`.
- **Element-wise gains:** Gains are arrays `[φ, θ, ψ]`; multiply element-wise (Hadamard), not matrix multiply, before the inertia `I @` scaling.
- **Mode changes:** Reset/decay the attitude integrator on mode transitions (takeoff→hover→land) to avoid carrying bias into a new regime.

## Tuning Guidelines

| Symptom | Fix |
|---|---|
| Slow roll/pitch correction | Increase `kp_att[0]` or `kp_att[1]` |
| Roll/pitch oscillates | Increase `kd_att[0]` or `kd_att[1]` |
| Yaw drifts slowly | Increase `ki_att[2]` |
| x/y oscillation during hover | Decrease `ki_att` |

## Integration in Main Loop

```python
att_integral = make_attitude_integral()   # once before the loop

for iter_ in range(max_iter - 1):
    ...
    desired_state.rot, desired_state.omega = attitude_planner(desired_state, params)
    M = attitude_controller(current_state, desired_state, params, att_integral)
```
