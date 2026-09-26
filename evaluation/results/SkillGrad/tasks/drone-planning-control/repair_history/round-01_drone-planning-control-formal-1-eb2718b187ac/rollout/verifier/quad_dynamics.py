from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np


def rotation_matrix_zyx(euler: np.ndarray) -> np.ndarray:
    phi, theta, psi = float(euler[0]), float(euler[1]), float(euler[2])
    cph, sph = np.cos(phi), np.sin(phi)
    cth, sth = np.cos(theta), np.sin(theta)
    cps, sps = np.cos(psi), np.sin(psi)

    # Rz(psi) * Ry(theta) * Rx(phi)
    return np.array(
        [
            [cps * cth, cps * sth * sph - sps * cph, cps * sth * cph + sps * sph],
            [sps * cth, sps * sth * sph + cps * cph, sps * sth * cph - cps * sph],
            [-sth, cth * sph, cth * cph],
        ],
        dtype=float,
    )


def prop_allocation_matrix(params: dict) -> np.ndarray:
    d = float(params["arm_length"])
    alpha = float(params.get("motor_spread_angle", np.pi / 4))
    cT = float(params["thrust_coefficient"])
    cQ = float(params["moment_scale"])

    # Motor xy positions (body frame)
    x = np.array([d * np.cos(alpha), -d * np.cos(alpha), -d * np.cos(alpha), d * np.cos(alpha)], dtype=float)
    y = np.array([d * np.sin(alpha), d * np.sin(alpha), -d * np.sin(alpha), -d * np.sin(alpha)], dtype=float)

    spin = np.array([-1.0, 1.0, -1.0, 1.0], dtype=float)

    A = np.zeros((4, 4), dtype=float)
    A[0, :] = cT
    A[1, :] = y * cT  # Mx = sum(y_i * T_i)
    A[2, :] = -x * cT  # My = sum(-x_i * T_i)
    A[3, :] = spin * cQ
    return A


def mix_to_rpm(params: dict, F: float, M: np.ndarray) -> np.ndarray:
    A = prop_allocation_matrix(params)
    u = np.array([float(F), float(M[0]), float(M[1]), float(M[2])], dtype=float)

    try:
        rpm_sq = np.linalg.solve(A, u)
    except np.linalg.LinAlgError:
        rpm_sq = np.linalg.lstsq(A, u, rcond=None)[0]

    rpm_sq = np.clip(rpm_sq, 0.0, None)
    rpm = np.sqrt(rpm_sq)

    rpm_min = float(params["rpm_min"])
    rpm_max = float(params["rpm_max"])
    rpm = np.clip(rpm, rpm_min, rpm_max)
    return rpm


def forces_moments_from_rpm(params: dict, rpm: np.ndarray) -> Tuple[float, np.ndarray]:
    A = prop_allocation_matrix(params)
    u = A @ (np.asarray(rpm, dtype=float) ** 2)
    return float(u[0]), np.array(u[1:4], dtype=float)


def state_derivative(params: dict, state: np.ndarray, rpm_des: np.ndarray) -> np.ndarray:
    state = np.asarray(state, dtype=float)
    rpm = state[12:16]

    km = float(params["motor_constant"])
    rpm_dot = km * (np.asarray(rpm_des, dtype=float) - rpm)

    F, M = forces_moments_from_rpm(params, rpm)

    m = float(params["mass"])
    g = float(params["gravity"])

    R = rotation_matrix_zyx(state[6:9])
    thrust_world = R @ np.array([0.0, 0.0, F / m], dtype=float)
    vel_dot = np.array([0.0, 0.0, -g], dtype=float) + thrust_world

    I = np.diag(np.asarray(params["inertia"], dtype=float))
    omega_dot = np.linalg.solve(I, M)

    sdot = np.zeros_like(state)
    sdot[0:3] = state[3:6]
    sdot[3:6] = vel_dot
    sdot[6:9] = state[9:12]
    sdot[9:12] = omega_dot
    sdot[12:16] = rpm_dot
    return sdot


def rk4_step(params: dict, state: np.ndarray, rpm_des: np.ndarray, dt: float) -> np.ndarray:
    s = np.asarray(state, dtype=float)
    k1 = state_derivative(params, s, rpm_des)
    k2 = state_derivative(params, s + 0.5 * dt * k1, rpm_des)
    k3 = state_derivative(params, s + 0.5 * dt * k2, rpm_des)
    k4 = state_derivative(params, s + dt * k3, rpm_des)
    return s + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
