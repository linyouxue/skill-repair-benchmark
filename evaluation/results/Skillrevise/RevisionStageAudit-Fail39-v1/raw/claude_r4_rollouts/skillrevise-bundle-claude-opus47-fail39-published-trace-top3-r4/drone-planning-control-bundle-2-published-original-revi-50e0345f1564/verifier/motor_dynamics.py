"""Motor model (allocation + first-order lag) and rigid-body dynamics."""

import numpy as np
from scipy.integrate import solve_ivp


def build_prop_matrix(params):
    cT = params['thrust_coefficient']
    cQ = params['moment_scale']
    d = params['arm_length'] * np.sin(params['motor_spread_angle'])
    return np.array([
        [ cT,     cT,     cT,     cT   ],
        [ 0.0,    d * cT, 0.0,   -d * cT],
        [-d * cT, 0.0,    d * cT, 0.0 ],
        [-cQ,     cQ,    -cQ,     cQ  ],
    ])


def motor_model(F_des, M_des, rpm_cur, prop_matrix, params):
    """Return (F_actual, M_actual, rpm_dot)."""
    rhs = np.array([F_des, M_des[0], M_des[1], M_des[2]])
    rpm_sq = np.linalg.solve(prop_matrix, rhs)
    rpm_sq = np.clip(rpm_sq, 0.0, None)
    rpm_des = np.sqrt(rpm_sq)
    rpm_des = np.clip(rpm_des, params['rpm_min'], params['rpm_max'])

    km = params['motor_constant']
    rpm_dot = km * (rpm_des - rpm_cur)

    actual = prop_matrix @ (rpm_cur ** 2)
    F_actual = float(actual[0])
    M_actual = actual[1:4].copy()
    return F_actual, M_actual, rpm_dot


def dynamics(state, F, M, rpm_dot, params):
    """16-state derivative."""
    g = params['gravity']
    m = params['mass']
    I_diag = np.asarray(params['inertia'], dtype=float)

    phi, theta, psi = state[6], state[7], state[8]
    p, q, r = state[9], state[10], state[11]

    cphi, sphi = np.cos(phi), np.sin(phi)
    cth, sth = np.cos(theta), np.sin(theta)
    cpsi, spsi = np.cos(psi), np.sin(psi)

    # Thrust direction in world frame (ZYX Euler)
    ax = (F / m) * (cpsi * sth * cphi + spsi * sphi)
    ay = (F / m) * (spsi * sth * cphi - cpsi * sphi)
    az = -g + (F / m) * cth * cphi

    omega_dot = M / I_diag  # diagonal inertia

    sd = np.zeros(16)
    sd[0:3] = state[3:6]
    sd[3] = ax
    sd[4] = ay
    sd[5] = az
    sd[6:9] = state[9:12]  # small-angle approx: Euler rate ≈ body rate
    sd[9:12] = omega_dot
    sd[12:16] = rpm_dot
    return sd


def integrate_step(state, F, M, rpm_dot, params, dt):
    """Advance one dt using RK45."""
    def rhs(t, s):
        return dynamics(s, F, M, rpm_dot, params)

    sol = solve_ivp(rhs, [0.0, dt], state, method='RK45', rtol=1e-6, atol=1e-8)
    return sol.y[:, -1]
