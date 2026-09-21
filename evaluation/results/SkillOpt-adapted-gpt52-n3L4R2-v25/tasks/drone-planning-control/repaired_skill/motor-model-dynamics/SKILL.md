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





## Dynamics (Equations of Motion)

### State vector (16,)

| Indices | Meaning |
|---|---|
| 0:3 | Position [x, y, z] |
| 3:6 | Velocity [vẋ, vẏ, vż] |
| 6:9 | Euler angles [φ, θ, ψ] |
| 9:12 | Angular velocity [p, q, r] |
| 12:16 | Motor RPM [ω₁, ω₂, ω₃, ω₄] |





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


## Motor Geometry, Conventions, and Allocation

Use a right-handed body frame with `x_b` forward, `y_b` left, and `z_b` upward. Use a world frame with `z_w` upward. `R_wb = Rz(ψ) Ry(θ) Rx(φ)` maps body vectors into world coordinates, and positive yaw, roll, and pitch follow the right-hand rule. The propellers lie in an X configuration at arm length `L` from the body center. Define `a = L / sqrt(2)` and number the motors as:

| Motor | `(x_i, y_i)` | rotation sign `s_i` |
|---|---:|---:|
| 1 | `( a,  a)` | `+1` |
| 2 | `( a, -a)` | `-1` |
| 3 | `(-a, -a)` | `+1` |
| 4 | `(-a,  a)` | `-1` |

The signs alternate, where `+1` is the configured positive reaction-torque direction when viewed along `+z_b`; reversing the physical convention requires changing all `s_i` consistently. Each motor produces upward body thrust `T_i = cT * n_i^2` and reaction moment `Q_i = s_i * cQ * n_i^2`, where `n_i` is the numeric RPM value and `cT` and `cQ` are calibrated for RPM-squared units. Do not silently mix RPM and rad/s; if SI angular speed is used instead, convert both constants and all limits consistently.

For `u = [n_1^2,n_2^2,n_3^2,n_4^2]^T` and `b = [F,M_x,M_y,M_z]^T`, use `b = A u` with

```text
A = [[ cT,     cT,     cT,     cT    ],
     [ a*cT,  -a*cT,  -a*cT,   a*cT ],
     [-a*cT,  -a*cT,   a*cT,   a*cT ],
     [ cQ,    -cQ,     cQ,    -cQ   ]]
```

The explicit inverse is:

```text
u1 = F/(4*cT) + Mx/(4*a*cT) - My/(4*a*cT) + Mz/(4*cQ)
u2 = F/(4*cT) - Mx/(4*a*cT) - My/(4*a*cT) - Mz/(4*cQ)
u3 = F/(4*cT) - Mx/(4*a*cT) + My/(4*a*cT) + Mz/(4*cQ)
u4 = F/(4*cT) + Mx/(4*a*cT) + My/(4*a*cT) - Mz/(4*cQ)
```

Clamp each requested squared speed to `[rpm_min^2, rpm_max^2]` before taking the square root, and clamp the resulting command again to `[rpm_min, rpm_max]`. Report the allocation saturation to the controller so infeasible force or moment requests are not treated as achieved.


## Motor Lag and Actual Wrench

The motor state is the physical RPM vector `n = [n_1,n_2,n_3,n_4]`, in the same units as `rpm_min` and `rpm_max`. Convert the requested wrench through the allocation inverse, apply per-motor clipping, and obtain `n_cmd`. Use the first-order lag

```text
n_dot = km * (n_cmd - n),       km = 36.5 s^-1
```

with `n` initialized and maintained within `[rpm_min,rpm_max]`. The actual wrench used by the dynamics is computed from the lagged state, not from `n_cmd`:

```text
T_i = cT*n_i^2
F_actual = sum(T_i)
Mx_actual = a*(T_1 - T_2 - T_3 + T_4)
My_actual = a*(-T_1 - T_2 + T_3 + T_4)
Mz_actual = cQ*(n_1^2 - n_2^2 + n_3^2 - n_4^2)
```

Thus `rpm_min = 3000`, `rpm_max = 20000`, and `km` define both the motor state limits and the motor response. The force and moment returned to the dynamics must always be the actual values above.


## Complete 16-State Equations and Integration

Let `X = [r_w, v_w, (φ,θ,ψ), (p,q,r), n]^T`, where position and velocity are world-frame vectors, and angular velocity `ω_b=[p,q,r]^T` is body-frame. With mass `m`, inertia `I`, and gravity magnitude `g`, define

```text
R = Rz(ψ) @ Ry(θ) @ Rx(φ)
r_dot = v_w
v_dot = [0, 0, -g] + R @ [0, 0, F_actual/m]
```

The body thrust direction is `+z_b`; gravity is world `[0,0,-g]`. Rigid-body rotational dynamics include the inertia cross terms:

```text
I*ω_dot = M_actual - cross(ω_b, I@ω_b)
ω_dot = inv(I) @ (M_actual - cross(ω_b, I@ω_b))
```

For ZYX Euler angles, use

```text
[φ_dot, θ_dot, ψ_dot]^T = [[1, sin(φ)*tan(θ),  cos(φ)*tan(θ)],
                            [0, cos(φ),         -sin(φ)        ],
                            [0, sin(φ)/cos(θ),  cos(φ)/cos(θ) ]] @ [p,q,r]^T
```

Reject or handle states with `|cos(θ)|` below a configured singularity threshold rather than allowing NaNs. The final four derivatives are the motor-lag derivatives `n_dot` above, so the derivative has exactly 16 elements in the state order documented in this skill. Integrate this complete derivative with an adaptive RK45 solver using the configured simulation timestep/output times; evaluate motor lag, actual wrench, rotation, and all cross terms at every RK45 substage. Do not integrate desired RPM or desired wrench as state variables.


## Physical Limits and Planner/Controller Interface

Compute the motor-derived force limits from the configured constants and RPM limits:

```text
T_min = 4*cT*rpm_min^2
T_max = 4*cT*rpm_max^2
twr = T_max/(m*g)
```

For level attitude, the corresponding vertical acceleration bounds are `(T_min/m - g)` and `(T_max/m - g)`; use the configured `accel_limit_up` and `accel_limit_down` only when they are no greater than these physically achievable bounds. Horizontal acceleration must also account for tilt and total-thrust limits: for a requested world acceleration `a_w`, require `F_required = m*(a_w - [0,0,-g])`, enforce `||F_required|| <= T_max`, and limit its horizontal component to `accel_limit_horiz`. Apply these checks at every planned timestep, including transitions, and expose the feasible acceleration envelope to both position and attitude controllers.

Convert planner and simulator states consistently to the required 15-row format: rows `0:3` position `r_w`, `3:6` world velocity `v_w`, `6:9` Euler angles `(φ,θ,ψ)`, `9:12` body angular velocity `(p,q,r)`, and `12:15` world linear acceleration `v_dot`. The actual acceleration row must be computed from the same actual wrench and rotation used by the dynamics, while the planned acceleration row must satisfy the physical limits before saving `planned_trajectory.npy`. Motor RPM is retained only in the internal 16-state vector and is not placed in the 15-row planner output.
