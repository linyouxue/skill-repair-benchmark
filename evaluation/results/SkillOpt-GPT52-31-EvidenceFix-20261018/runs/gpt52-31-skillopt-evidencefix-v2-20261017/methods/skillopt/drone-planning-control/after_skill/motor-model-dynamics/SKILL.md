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

### Propeller Allocation Matrix (X-frame quadrotor)

The 4×4 allocation matrix maps `[F, Mx, My, Mz]` to squared motor RPMs. For an X-frame with arm length `d`, thrust coefficient `cT`, and torque coefficient `cQ`:



**Conventions (must be consistent everywhere):**

- **Body frame:** x forward, y left, z up (right-handed). Moments `[Mx, My, Mz]` are about body x/y/z.
- **Motor ordering (1..4):** front-left (CCW), front-right (CW), rear-right (CCW), rear-left (CW) for an X-frame.
- **Yaw sign:** `+Mz` corresponds to CCW yaw acceleration about +z. With the above spin directions, CCW rotors contribute `+cQ·rpm^2` to `Mz` and CW rotors contribute `−cQ·rpm^2` (or equivalently use the row shown below).

If your code uses a different axis convention (e.g., z down or y right), you must flip the appropriate signs in the allocation matrix *and* in the dynamics rotation/moment equations.

```
         motor:  1      2      3      4
Thrust:         +cT    +cT    +cT    +cT
Roll  (Mx):      0    +d·cT    0    -d·cT
Pitch (My):    -d·cT    0    +d·cT    0
Yaw   (Mz):    -cQ    +cQ    -cQ    +cQ
```

### Implementation Logic

1. Build the 4×4 `prop_matrix` from `cT`, `cQ`, and `d` using the motor ordering and sign conventions above.
2. Solve `prop_matrix @ rpm_sq_cmd = [F_cmd, Mx_cmd, My_cmd, Mz_cmd]` for `rpm_sq_cmd`.
   - Prefer a numerically stable solve: `np.linalg.solve` if well-conditioned; otherwise use least-squares/pseudoinverse (`np.linalg.lstsq` / `np.linalg.pinv`) and document it.
3. **Physics hardening:** clamp squared speeds to be nonnegative **before** taking square roots:
   - `rpm_sq_cmd = np.maximum(rpm_sq_cmd, 0.0)`
   - `rpm_cmd = np.sqrt(rpm_sq_cmd)`
4. Clip commanded RPM to physical limits:
   - `rpm_cmd = np.clip(rpm_cmd, rpm_min, rpm_max)`
5. Apply first-order motor lag on RPM state:
   - `rpm_dot = km * (rpm_cmd - rpm_current)`
   - Integrate RPM as part of the full state (or consistently inside the motor model).
6. **After clipping/lag, recompute achieved wrench** from the *actual* RPM used by dynamics:
   - `wrench_actual = prop_matrix @ (rpm_actual ** 2)`
   - Return `F_actual = wrench_actual[0]`, `M_actual = wrench_actual[1:4]`.

Note: Controllers may request infeasible `[F,M]`; after clipping, `wrench_actual` can differ significantly from the command. Always feed the recomputed achieved `F_actual, M_actual` into the dynamics for consistency.

## Dynamics (Equations of Motion)

### State vector (16,)

| Indices | Meaning |
|---|---|
| 0:3 | Position [x, y, z] |
| 3:6 | Velocity [vẋ, vẏ, vż] |
| 6:9 | Euler angles [φ, θ, ψ] |
| 9:12 | Angular velocity [p, q, r] |
| 12:16 | Motor RPM [ω₁, ω₂, ω₃, ω₄] |

### Implementation Logic

Compute `state_dot` (16,) from current state and applied forces/moments (all expressed in **body** unless stated):

1. **Position derivative (world frame)**
   - `pos_dot = vel_world = state[3:6]`.
2. **Translational acceleration (world frame)**
   - Form rotation `R_wb` from ZYX Euler angles `[φ, θ, ψ]` that maps body vectors → world vectors.
   - Thrust acts along body +z: `f_body = [0, 0, F_actual]`.
   - `acc_world = (R_wb @ f_body) / m + [0, 0, -g]`.
   - Set `vel_dot = acc_world`.
3. **Euler angle rates (do NOT set equal to body rates)**
   - Let body rates be `ω = [p, q, r] = state[9:12]`.
   - Use the standard ZYX mapping: `[φ_dot, θ_dot, ψ_dot]^T = E(φ,θ) @ ω`, where
     ```
     E(φ,θ) = [[1, sinφ*tanθ,  cosφ*tanθ],
              [0, cosφ,      -sinφ     ],
              [0, sinφ/secθ,  cosφ/secθ]]
     ```
   - Guard against `cos(θ) → 0` singularity (limit pitch in planners/controllers or clamp `θ`).
4. **Rotational dynamics (body frame)**
   - Rigid-body equation: `ω_dot = I^{-1} ( M_actual - ω × (I ω) )`.
5. **Motor RPM derivative**
   - `rpm_dot = km * (rpm_cmd_clipped - rpm_current)` from the motor model.

The moments `M_actual` must match the body axes used by `ω` and `I`.

## RK45 Integration

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



## Numerical Stability and Unit Notes

- **Units:** Be explicit whether motor speed is stored as RPM or rad/s.
  - If using RPM in state, ensure `cT`/`cQ` are calibrated for RPM-based formulas (`T = cT·rpm^2`, `Q = cQ·rpm^2`).
  - If converting to rad/s, use `ω_rad = rpm * 2π/60` and adjust coefficients accordingly.
- **Allocation conditioning:** Near-hover and aggressive maneuvers can make the solve sensitive. Prefer `np.linalg.solve` when the matrix is well-conditioned; otherwise use least-squares and consider regularization.
- **Clipping consistency:** Always recompute achieved `[F,M]` from clipped/lagged RPM before applying to dynamics.
- **Motor lag constant:** Typical quad motor time constants are on the order of 20–80 ms (km ≈ 12–50 s⁻¹). Too small `km` makes the system sluggish; too large makes it stiff.
- **Integration step sizing:** Keep the integration step aligned with `sample_rate` (e.g., `dt = 1/sample_rate`). If RK45 shows stiffness due to high `km`, consider reducing `dt` or using a stiff solver (Radau/BDF) for the physics layer.
