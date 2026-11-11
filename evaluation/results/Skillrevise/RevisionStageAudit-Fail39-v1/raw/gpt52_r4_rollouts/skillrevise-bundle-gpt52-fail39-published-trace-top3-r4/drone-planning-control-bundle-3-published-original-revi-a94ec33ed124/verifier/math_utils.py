from __future__ import annotations

import numpy as np


def wrap_pi(angle: float) -> float:
    return (angle + np.pi) % (2 * np.pi) - np.pi


def euler_to_R(roll: float, pitch: float, yaw: float) -> np.ndarray:
    cr, sr = np.cos(roll), np.sin(roll)
    cp, sp = np.cos(pitch), np.sin(pitch)
    cy, sy = np.cos(yaw), np.sin(yaw)

    # ZYX: R = Rz(yaw) Ry(pitch) Rx(roll)
    return np.array(
        [
            [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
            [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
            [-sp, cp * sr, cp * cr],
        ],
        dtype=float,
    )


def R_to_euler(R: np.ndarray) -> np.ndarray:
    # ZYX extraction with mild numerical guarding.
    sp = -float(R[2, 0])
    sp = float(np.clip(sp, -1.0, 1.0))
    pitch = np.arcsin(sp)

    cp = np.cos(pitch)
    if abs(cp) < 1e-6:
        # Near gimbal lock; fall back to yaw from R[0,1]/R[1,1].
        roll = 0.0
        yaw = np.arctan2(-R[0, 1], R[1, 1])
    else:
        roll = np.arctan2(R[2, 1] / cp, R[2, 2] / cp)
        yaw = np.arctan2(R[1, 0] / cp, R[0, 0] / cp)

    return np.array([roll, pitch, yaw], dtype=float)


def body_rates_to_euler_rates(euler: np.ndarray, omega_body: np.ndarray) -> np.ndarray:
    roll, pitch, _ = float(euler[0]), float(euler[1]), float(euler[2])
    p, q, r = float(omega_body[0]), float(omega_body[1]), float(omega_body[2])

    cr, sr = np.cos(roll), np.sin(roll)
    ct = np.cos(pitch)
    st = np.sin(pitch)

    ct_safe = float(ct) if abs(ct) > 1e-6 else (1e-6 if ct >= 0 else -1e-6)

    phi_dot = p + sr * st / ct_safe * q + cr * st / ct_safe * r
    theta_dot = cr * q - sr * r
    psi_dot = sr / ct_safe * q + cr / ct_safe * r
    return np.array([phi_dot, theta_dot, psi_dot], dtype=float)


def clamp_vector_horiz(acc_xy: np.ndarray, limit: float) -> np.ndarray:
    n = float(np.linalg.norm(acc_xy))
    if n <= limit or n < 1e-12:
        return acc_xy
    return acc_xy * (limit / n)
