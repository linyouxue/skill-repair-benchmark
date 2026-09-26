from __future__ import annotations

import numpy as np


def rot_matrix_from_euler(phi: float, theta: float, psi: float) -> np.ndarray:
    cphi, sphi = np.cos(phi), np.sin(phi)
    cth, sth = np.cos(theta), np.sin(theta)
    cpsi, spsi = np.cos(psi), np.sin(psi)

    # ZYX convention: R = Rz(psi) Ry(theta) Rx(phi)
    return np.array(
        [
            [cpsi * cth, cpsi * sth * sphi - spsi * cphi, cpsi * sth * cphi + spsi * sphi],
            [spsi * cth, spsi * sth * sphi + cpsi * cphi, spsi * sth * cphi - cpsi * sphi],
            [-sth, cth * sphi, cth * cphi],
        ],
        dtype=float,
    )


def euler_from_rot_matrix(R: np.ndarray) -> np.ndarray:
    # Inverse of rot_matrix_from_euler for ZYX.
    # theta = -asin(R[2,0])
    r20 = float(R[2, 0])
    r20 = np.clip(r20, -1.0, 1.0)
    theta = -np.arcsin(r20)

    cth = np.cos(theta)
    if abs(cth) < 1e-8:
        # Gimbal lock; pick psi=0
        phi = np.arctan2(-R[0, 1], R[1, 1])
        psi = 0.0
    else:
        phi = np.arctan2(R[2, 1], R[2, 2])
        psi = np.arctan2(R[1, 0], R[0, 0])

    return np.array([phi, theta, psi], dtype=float)


def wrap_angle(angle: float) -> float:
    return (angle + np.pi) % (2 * np.pi) - np.pi


def wrap_angles(v: np.ndarray) -> np.ndarray:
    out = np.array(v, dtype=float)
    out[0] = wrap_angle(out[0])
    out[1] = wrap_angle(out[1])
    out[2] = wrap_angle(out[2])
    return out
