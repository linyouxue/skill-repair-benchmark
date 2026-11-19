---
name: motor-model-dynamics
description: Use this skill when simulating quadrotor physical dynamics — mapping desired thrust/moments to individual motor RPMs via an allocation matrix, applying motor lag and saturation, and integrating the nonlinear equations of motion (translational and rotational) at the control timestep.
---

# Motor Model and Dynamics Simulation

## Overview

Two modules form the physics layer of the simulator:

1. **Motor model** — maps desired `[F, Mx, My, Mz]` → desired motor RPMs → applies first-order lag → returns actual thrust and moments
2. **Dynamics** — nonlinear equations of motion; given forces and moments, returns the 16-element state derivative for ODE integration

## Motor Model

### Propeller Allocation Matrix (X-frame quadrotor)

The 4×4 allocation matrix maps motor **squared speed** to total thrust and body moments.

A robust way to derive it (and avoid sign mistakes) is to start from geometry. For each motor located at planar position `r_i = [x_i, y_i, 0]` in the body frame, with thrust `T_i = cT · ω_i²` along `+body_z`, the moment from that thrust is:

- `r_i × [0, 0, T_i] = [y_i · T_i, −x_i · T_i, 0]`

and the reaction yaw moment is `±cQ · ω_i²` depending on spin direction.

So the allocation has the general form:

```
[ F  ]   [ cT        cT        cT        cT      ] [ ω1² ]
[ Mx ] = [ y1·cT     y2·cT     y3·cT     y4·cT   ] [ ω2² ]
[ My ]   [ −x1·cT    −x2·cT    −x3·cT    −x4·cT  ] [ ω3² ]
[ Mz ]   [ s1·cQ     s2·cQ     s3·cQ     s4·cQ   ] [ ω4² ]
```

where `s_i ∈ {−1, +1}` encodes the motor spin directions.

For an X-frame parameterised by `arm_length = d` and `motor_spread_angle = α`, you can set `x = d·cos(α)`, `y = d·sin(α)` and use motor positions like `(+x,+y), (−x,+y), (−x,−y), (+x,−y)`.

### Implementation Logic

1. Build the 4×4 allocation matrix from the parameters in `system_params.yaml`:
   - `thrust_coefficient` (often denoted `cT`)
   - `moment_scale` (torque/yaw coefficient; often denoted `cQ`)
   - `arm_length` (lever arm)
   - (If using an X-frame model, include the `motor_spread_angle` if your geometry needs it.)
2. Solve `A @ rpm_sq = [F, Mx, My, Mz]` for `rpm_sq` (desired squared RPMs).
3. Clamp `rpm_sq` to be non-negative before taking square-roots.
4. Clip RPM to `[rpm_min, rpm_max]`.
5. Apply first-order motor lag: `rpm_dot = motor_constant * (rpm_desired - rpm_current)`.
6. Compute actual force/moment using `A @ (rpm_actual ** 2)` and return both `(F_actual, M_actual)` plus `rpm_dot`.

Notes:
- Always use the parameter names from the config (`moment_scale`, `motor_constant`, `motor_spread_angle`, etc.) rather than inventing new ones.
- In some provided parameter files `moment_scale` is **already `cQ`** (~1e−10). In others it may be a dimensionless ratio such as `cQ/cT`. If you see yaw response off by orders of magnitude, validate which convention is being used.
- Saturation (rpm limits) is part of the dynamics and will dominate tracking if your planner requests accelerations that exceed limits.

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

Compute `state_dot` (16,) from current state and applied forces/moments:

1. **Position derivative** = current velocity (`state[3:6]`).
2. **Velocity derivative** = gravity + thrust projected into world frame via ZYX Euler rotation. The x/y accelerations depend on `F/m`, `sin`/`cos` of all three Euler angles. The z acceleration is `−g + (F/m)·cos(φ)·cos(θ)`.
3. **Euler angle derivative** depends on what you store in `state[9:12]`:
   - If `state[9:12]` are Euler-angle rates, then `euler_dot = state[9:12]` is consistent.
   - If they are body rates `[p,q,r]`, you need the ZYX kinematic mapping from body rates to Euler rates.

Pick one convention and keep it consistent with your controller.
4. **Angular velocity derivative** = `I⁻¹ M` (solve inertia matrix against moment vector).
5. **Motor RPM derivative** = `rpm_motor_dot` from the motor model.

## Integration

For this task, a simple explicit integrator at the control timestep is usually sufficient and much faster than calling an ODE solver at every 5 ms step:

- `state_next = state + state_dot * dt` (Euler)
- or a small fixed-step RK2/RK4 if you need extra stability.

If you do use `solve_ivp`, avoid re-solving tiny intervals in a tight Python loop unless you have a strong reason.

## Motor Physical Limits

| Parameter | Value | Meaning |
|---|---|---|
| `rpm_min` | 3000 | Minimum motor speed (motors always spinning) |
| `rpm_max` | 20000 | Maximum motor speed |
| `motor_constant` | 36.5 s⁻¹ | First-order motor lag constant; τ = 1/motor_constant ≈ 27 ms |

## Thrust/Acceleration Limits

You can derive thrust limits from the RPM limits:

- `T_max = 4 * cT * rpm_max^2`
- `T_min = 4 * cT * rpm_min^2`

But in this benchmark the planner is expected to respect the precomputed limits already provided in `system_params.yaml`:

- `accel_limit_up`, `accel_limit_down`, `accel_limit_horiz`

Use these values for trajectory feasibility checks, and treat motor saturation as a last-resort safety effect rather than something you rely on for nominal tracking.
