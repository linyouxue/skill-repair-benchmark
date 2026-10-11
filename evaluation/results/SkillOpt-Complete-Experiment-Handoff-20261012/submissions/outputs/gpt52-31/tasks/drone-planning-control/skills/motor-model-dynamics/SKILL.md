---
name: motor-model-dynamics
description: Use this skill when simulating quadrotor physical dynamics — mapping desired thrust/moments to individual motor RPMs via a propeller allocation matrix, applying first-order motor lag, and integrating the nonlinear equations of motion (translational and rotational) using RK45.
---

# Motor Model and Dynamics Simulation

## Overview

Two modules form the physics layer of the simulator:

1. **Motor model** — maps desired `[F, Mx, My, Mz]` → desired motor RPMs → applies first-order lag → returns actual thrust and moments
2. **Dynamics** — nonlinear equations of motion; given forces and moments, returns the 16-element state derivative for ODE integration

## Motor Model



### Frame, Sign, and Ordering Conventions (must match planner/controllers)

Use these conventions consistently across allocation, dynamics, and controllers:

- **World/inertial frame (W)**: ENU with **+z up**.
- **Body frame (B)**: **x forward**, **y left**, **z up** (right-handed).
- **Euler angles**: ZYX (yaw ψ about +z, pitch θ about +y, roll φ about +x). Rotation **R_WB(φ,θ,ψ)** maps body vectors to world: `v_W = R_WB @ v_B`.
- **Gravity**: acceleration in world is `a_g = [0, 0, -g]`.
- **Thrust direction**: total thrust force acts along **+z_B** (up in body). Thus `F_B = [0, 0, F]` with `F >= 0`.
- **Command vector ordering** everywhere in this skill: `u = [F, Mx, My, Mz]` where moments are in **body frame** about **x_B,y_B,z_B**.
- **Motor ordering** for the allocation matrix tables below is **[1,2,3,4] exactly as shown**. If code uses a different numbering, **permute rows/cols** accordingly so the mapping remains consistent.

### Propeller Allocation Matrix (X-frame quadrotor)

The 4×4 allocation matrix maps `[F, Mx, My, Mz]` to squared motor RPMs. For an X-frame with arm length `d`, thrust coefficient `cT`, and torque coefficient `cQ`:

```
         motor:  1      2      3      4
Thrust:         +cT    +cT    +cT    +cT
Roll  (Mx):      0    +d·cT    0    -d·cT
Pitch (My):    -d·cT    0    +d·cT    0
Yaw   (Mz):    -cQ    +cQ    -cQ    +cQ
```

### Implementation Logic

1. Build the 4×4 `prop_matrix` from `cT`, `cQ`, and `d`.
2. Solve `prop_matrix @ rpm_sq = [F, Mx, My, Mz]` for `rpm_sq` (desired squared RPMs).
3. Take `sqrt` of each element (clamp negatives to 0 first), then clip to `[rpm_min, rpm_max]`.
4. Apply first-order motor lag: `rpm_dot = km * (rpm_desired - rpm_current)`.
5. Compute actual force/moment using `prop_matrix @ (motor_rpm ** 2)` and return `(F_actual, M_actual, rpm_dot)`.



### Saturation, infeasible commands, and numerically-stable clipping

When solving for `rpm_sq`:

- **Negative components**: after solving `rpm_sq`, apply `rpm_sq = maximum(rpm_sq, 0)` before `sqrt`.
- **Saturation**: clip **rpm** (not rpm_sq) to `[rpm_min, rpm_max]`, then recompute achieved wrench:
  - `rpm = clip(sqrt(rpm_sq), rpm_min, rpm_max)`
  - `u_achieved = prop_matrix @ (rpm**2)`
- **Infeasible wrench** (e.g., commanded moments too large for given F): the achieved `u_achieved` should be what is fed into dynamics. Optionally log/return the residual `u_cmd - u_achieved` for debugging/tuning.
- **Avoid sign ambiguity**: `F` is **nonnegative** thrust magnitude along +z_B. Downward acceleration is achieved by reducing `F` toward `T_min`, not by negative thrust.

## Dynamics (Equations of Motion)

### State vector (16,)

| Indices | Meaning |
|---|---|
| 0:3 | Position [x, y, z] |
| 3:6 | Velocity [vẋ, vẏ, vż] |
| 6:9 | Euler angles [φ, θ, ψ] |
| 9:12 | Angular velocity [p, q, r] |
| 12:16 | Motor RPM [ω₁, ω₂, ω₃, ω₄] |

### Implementation Logic (explicit 16-state derivative)

Compute `state_dot` (16,) from current state and applied forces/moments using the conventions above.

Let the state be:
- `p_W = [x,y,z]` (world position)
- `v_W = [vx,vy,vz]` (world linear velocity)
- `e = [φ,θ,ψ]` (roll, pitch, yaw)
- `ω_B = [p,q,r]` (body angular rate)
- `rpm = [ω1,ω2,ω3,ω4]` (motor speeds)

1) **Position**
- `ṗ_W = v_W`

2) **Translational dynamics (world frame)**
- Body thrust force: `F_B = [0, 0, F_actual]`
- Rotation `R_WB(φ,θ,ψ)` (ZYX) maps body→world.
- Linear acceleration:
  - `v̇_W = (1/m) * (R_WB @ F_B) + [0, 0, -g]`
  - This yields `z̈ = -g + (F_actual/m)*cos(φ)*cos(θ)` under ZYX.

3) **Euler angle kinematics (ZYX)**
Euler rates are **not** equal to body rates. Use:

`[φ̇, θ̇, ψ̇]^T = T(φ,θ) @ [p,q,r]^T`, where

```
T(φ,θ) = [[1,  sinφ*tanθ,  cosφ*tanθ],
          [0,       cosφ,       -sinφ],
          [0,  sinφ/secθ,  cosφ/secθ]]
```
with `secθ = 1/cosθ`. Guard against `|cosθ|` near 0 (gimbal lock) by limiting `θ` to a safe range (e.g., `|θ| < π/2 - 1e-3`) or switching to quaternions in code.

4) **Rotational dynamics (body frame)**
Let inertia matrix be `I` in body frame. Rigid body equation:
- `ω̇_B = I^{-1} * ( M_actual - ω_B × (I @ ω_B) )`

5) **Motor dynamics**
- `rpṁ = rpm_motor_dot` from the motor model (first-order lag).

Finally assemble:
- `state_dot[0:3]=ṗ_W`, `[3:6]=v̇_W`, `[6:9]=[φ̇,θ̇,ψ̇]`, `[9:12]=ω̇_B`, `[12:16]=rpṁ`.

## RK45 Integration



### Controller-to-ODE synchronization and numerical hygiene

- **Zero-order hold inputs**: hold `u_cmd` (or equivalently `F_actual, M_actual`) constant over `[t_k, t_{k+1}]` for each control timestep `dt`.
- **Motor lag inside ODE**: best practice is to compute `rpṁ = km*(rpm_des - rpm)` **inside** the ODE using the held `rpm_des` for the interval, so RK45 integrates motor states consistently with translation/rotation.
- **Angle wrapping**: after each integration step, normalize yaw `ψ` to `(-π, π]` (and optionally roll as well). Keep pitch `θ` within a safe bound to avoid `tanθ` blow-up.
- **RK45 tolerances**: use reasonable tolerances (e.g., `rtol=1e-6`, `atol=1e-8`) and set `t_eval=[t_{k+1}]` or take the final state from the solver.
- **Clipping forces/moments**: do not directly clip `F_actual`/`M_actual`; clip motor rpm and recompute the achieved wrench via the allocation matrix to maintain physical consistency.

Use `scipy.integrate.solve_ivp` with `method='RK45'` over each timestep `[t_k, t_{k+1}]`. The ODE function wraps `dynamics(params, s, F_actual, M_actual, rpm_motor_dot)` with `F_actual` and `M_actual` held constant for the step. After solving, take the last column of `sol.y` as the new state.

## Motor Physical Limits

| Parameter | Value | Meaning |
|---|---|---|
| `rpm_min` | 3000 | Minimum motor speed (motors always spinning) |
| `rpm_max` | 20000 | Maximum motor speed |
| `motor_constant` km | 36.5 s⁻¹ | First-order time constant; τ = 1/km ≈ 27 ms |

## Max Thrust Calculation

Derived from motor limits:
- `T_max = 4 * cT * rpm_max²` (all 4 motors at max RPM)
- `T_min = 4 * cT * rpm_min²`
- Thrust-to-weight ratio: `twr = T_max / (mass * gravity)`
- Max upward acceleration: `(T_max − mass·g) / mass`
- Max downward acceleration: `(mass·g − T_min) / mass`
