from __future__ import annotations

import numpy as np


def make_prop_matrix(params: dict) -> np.ndarray:
    cT = float(params['thrust_coefficient'])
    cQ = float(params['moment_scale'])
    d = float(params['arm_length'])

    return np.array(
        [
            [cT, cT, cT, cT],
            [0.0, d * cT, 0.0, -d * cT],
            [-d * cT, 0.0, d * cT, 0.0],
            [-cQ, cQ, -cQ, cQ],
        ],
        dtype=float,
    )


def motor_model(params: dict, motor_rpm: np.ndarray, F_des: float, M_des: np.ndarray):
    prop = make_prop_matrix(params)

    u = np.array([F_des, float(M_des[0]), float(M_des[1]), float(M_des[2])], dtype=float)
    rpm_sq = np.linalg.solve(prop, u)
    rpm_sq = np.maximum(rpm_sq, 0.0)

    rpm_des = np.sqrt(rpm_sq)
    rpm_des = np.clip(rpm_des, float(params['rpm_min']), float(params['rpm_max']))

    km = float(params['motor_constant'])
    rpm_dot = km * (rpm_des - motor_rpm)

    dt = 1.0 / float(params['sample_rate'])
    rpm_mid = np.clip(
        motor_rpm + 0.5 * rpm_dot * dt,
        float(params['rpm_min']),
        float(params['rpm_max']),
    )

    FM = prop @ (rpm_mid**2)
    F_act = float(FM[0])
    M_act = FM[1:4].astype(float)

    return F_act, M_act, rpm_dot


def accel_from_thrust(params: dict, rot: np.ndarray, F: float) -> np.ndarray:
    phi, theta, psi = float(rot[0]), float(rot[1]), float(rot[2])
    m = float(params['mass'])
    g = float(params['gravity'])

    ax = (F / m) * (np.cos(phi) * np.sin(theta) * np.cos(psi) + np.sin(phi) * np.sin(psi))
    ay = (F / m) * (np.cos(phi) * np.sin(theta) * np.sin(psi) - np.sin(phi) * np.cos(psi))
    az = -g + (F / m) * np.cos(phi) * np.cos(theta)
    return np.array([ax, ay, az], dtype=float)


def dynamics(params: dict, state: np.ndarray, F: float, M: np.ndarray, rpm_dot: np.ndarray) -> np.ndarray:
    state = np.asarray(state, dtype=float)

    vel = state[3:6]
    rot = state[6:9]
    omega = state[9:12]

    acc = accel_from_thrust(params, rot, F)

    I = np.asarray(params['inertia_matrix'], dtype=float)
    omega_dot = np.linalg.solve(I, np.asarray(M, dtype=float))

    out = np.zeros_like(state)
    out[0:3] = vel
    out[3:6] = acc
    out[6:9] = omega
    out[9:12] = omega_dot
    out[12:16] = rpm_dot
    return out


def step_dynamics_rk45(params: dict, state: np.ndarray, F: float, M: np.ndarray, rpm_dot: np.ndarray):
    dt = 1.0 / float(params['sample_rate'])

    k1 = dynamics(params, state, F, M, rpm_dot)
    k2 = dynamics(params, state + 0.5 * dt * k1, F, M, rpm_dot)
    k3 = dynamics(params, state + 0.5 * dt * k2, F, M, rpm_dot)
    k4 = dynamics(params, state + dt * k3, F, M, rpm_dot)

    s_next = state + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    s_next[12:16] = np.clip(s_next[12:16], float(params['rpm_min']), float(params['rpm_max']))
    return s_next
