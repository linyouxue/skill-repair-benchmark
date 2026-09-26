from __future__ import annotations

import numpy as np

from rotations import rot_matrix_from_euler


def dynamics(params: dict, state: np.ndarray, F: float, M: np.ndarray, rpm_dot: np.ndarray) -> np.ndarray:
    """State derivative for [pos(3), vel(3), euler(3), omega(3), motor_rpm(4)]."""

    mass = float(params["mass"])
    gravity = float(params["gravity"])
    invI = params["inv_inertia_matrix"]

    s = np.array(state, dtype=float).reshape(16)
    pos = s[0:3]
    vel = s[3:6]
    rot = s[6:9]
    omega = s[9:12]

    phi, theta, psi = map(float, rot)
    R = rot_matrix_from_euler(phi, theta, psi)

    # Translational dynamics: a = -g e3 + (F/m) * R e3
    thrust_world = (float(F) / mass) * (R @ np.array([0.0, 0.0, 1.0]))
    acc = np.array([0.0, 0.0, -gravity], dtype=float) + thrust_world

    # Rotational dynamics (simplified): omega_dot = invI * M
    omega_dot = invI @ np.array(M, dtype=float).reshape(3)

    sd = np.zeros(16, dtype=float)
    sd[0:3] = vel
    sd[3:6] = acc
    sd[6:9] = omega
    sd[9:12] = omega_dot
    sd[12:16] = np.array(rpm_dot, dtype=float).reshape(4)

    return sd
