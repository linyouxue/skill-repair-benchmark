from __future__ import annotations

from typing import Tuple

import numpy as np

from motor_model import motor_model


def euler_to_rot(phi: float, theta: float, psi: float) -> np.ndarray:
    cphi = np.cos(phi)
    sphi = np.sin(phi)
    cth = np.cos(theta)
    sth = np.sin(theta)
    cps = np.cos(psi)
    sps = np.sin(psi)

    # ZYX: Rz(psi) @ Ry(theta) @ Rx(phi)
    return np.array(
        [
            [cps * cth, cps * sth * sphi - sps * cphi, cps * sth * cphi + sps * sphi],
            [sps * cth, sps * sth * sphi + cps * cphi, sps * sth * cphi - cps * sphi],
            [-sth, cth * sphi, cth * cphi],
        ],
        dtype=float,
    )


def dynamics_derivative(params: dict, state: np.ndarray, F_des: float, M_des: np.ndarray) -> np.ndarray:
    """Compute x_dot for 16-state vector.

    state layout (16,):
      0:3 pos, 3:6 vel, 6:9 euler, 9:12 omega, 12:16 motor rpm
    """

    state = np.asarray(state, dtype=float).reshape(16)

    m = float(params["mass"])
    g = float(params["gravity"])
    I = np.diag(np.asarray(params["inertia"], dtype=float).reshape(3))
    I_inv = np.diag(1.0 / np.diag(I))

    pos = state[0:3]
    vel = state[3:6]
    rot = state[6:9]
    omega = state[9:12]
    rpm = state[12:16]

    F_act, M_act, rpm_dot = motor_model(params, rpm, F_des, M_des)

    R = euler_to_rot(rot[0], rot[1], rot[2])
    thrust_world = R @ np.array([0.0, 0.0, F_act], dtype=float)
    acc = thrust_world / m + np.array([0.0, 0.0, -g], dtype=float)

    # Euler angle rates approximation (sufficient for this simulator)
    rot_dot = omega

    # Rigid body rotational dynamics (slightly more stable than I^-1 M alone)
    omega_dot = I_inv @ (M_act - np.cross(omega, I @ omega))

    xdot = np.zeros((16,), dtype=float)
    xdot[0:3] = vel
    xdot[3:6] = acc
    xdot[6:9] = rot_dot
    xdot[9:12] = omega_dot
    xdot[12:16] = rpm_dot
    return xdot


def rk4_step(params: dict, state: np.ndarray, dt: float, F_des: float, M_des: np.ndarray) -> np.ndarray:
    state = np.asarray(state, dtype=float).reshape(16)
    k1 = dynamics_derivative(params, state, F_des, M_des)
    k2 = dynamics_derivative(params, state + 0.5 * dt * k1, F_des, M_des)
    k3 = dynamics_derivative(params, state + 0.5 * dt * k2, F_des, M_des)
    k4 = dynamics_derivative(params, state + dt * k3, F_des, M_des)
    return state + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)


def state16_to_state15(params: dict, state16: np.ndarray, F_act: float) -> np.ndarray:
    """Convert internal (16,) state to (15,) state vector used for logging."""

    m = float(params["mass"])
    g = float(params["gravity"])

    s = np.asarray(state16, dtype=float).reshape(16)
    out = np.zeros((15,), dtype=float)
    out[0:3] = s[0:3]
    out[3:6] = s[3:6]
    out[6:9] = s[6:9]
    out[9:12] = s[9:12]

    R = euler_to_rot(s[6], s[7], s[8])
    acc = (R @ np.array([0.0, 0.0, F_act], dtype=float)) / m + np.array([0.0, 0.0, -g], dtype=float)
    out[12:15] = acc
    return out
