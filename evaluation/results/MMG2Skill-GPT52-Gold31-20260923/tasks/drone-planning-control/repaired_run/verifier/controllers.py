from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np


def make_position_integral() -> Dict[str, np.ndarray]:
    return {"e": np.zeros(3, dtype=float)}


def make_attitude_integral() -> Dict[str, np.ndarray]:
    return {"e": np.zeros(3, dtype=float)}


def _clip_accel_limits(params: dict, acc_cmd: np.ndarray) -> np.ndarray:
    up = float(params["accel_limit_up"])
    down = float(params["accel_limit_down"])
    horiz = float(params["accel_limit_horiz"])

    acc_cmd = np.asarray(acc_cmd, dtype=float).reshape(3)
    acc_cmd[2] = float(np.clip(acc_cmd[2], -down, up))

    axy = acc_cmd[0:2]
    n = float(np.linalg.norm(axy))
    if n > horiz:
        acc_cmd[0:2] = axy * (horiz / n)
    return acc_cmd


def position_controller(
    current_state: np.ndarray,
    desired_state: np.ndarray,
    params: dict,
    integral: Dict[str, np.ndarray],
    kp: np.ndarray,
    ki: np.ndarray,
    kd: np.ndarray,
) -> Tuple[float, np.ndarray]:
    """Outer loop: position/velocity errors -> thrust magnitude and accel command."""

    dt = 1.0 / float(params["sample_rate"])

    pos = current_state[0:3]
    vel = current_state[3:6]

    pos_des = desired_state[0:3]
    vel_des = desired_state[3:6]
    acc_des = desired_state[12:15]

    pos_err = pos - pos_des
    vel_err = vel - vel_des

    integral["e"] = integral["e"] + pos_err * dt

    kp = np.asarray(kp, dtype=float).reshape(3)
    ki = np.asarray(ki, dtype=float).reshape(3)
    kd = np.asarray(kd, dtype=float).reshape(3)

    acc_cmd = acc_des - kp * pos_err - ki * integral["e"] - kd * vel_err
    acc_cmd = _clip_accel_limits(params, acc_cmd)

    m = float(params["mass"])
    g = float(params["gravity"])

    thrust_vec = m * (acc_cmd + np.array([0.0, 0.0, g], dtype=float))
    F_des = float(np.linalg.norm(thrust_vec))

    # Clip thrust to motor capabilities.
    cT = float(params["thrust_coefficient"])
    rpm_min = float(params["rpm_min"])
    rpm_max = float(params["rpm_max"])
    T_min = 4.0 * cT * rpm_min * rpm_min
    T_max = 4.0 * cT * rpm_max * rpm_max
    F_des = float(np.clip(F_des, T_min, T_max))

    return F_des, acc_cmd


def _rotmat_to_euler_zyx(R: np.ndarray) -> np.ndarray:
    # ZYX: R = Rz(psi) @ Ry(theta) @ Rx(phi)
    # theta = -asin(R[2,0])
    theta = -np.arcsin(np.clip(R[2, 0], -1.0, 1.0))
    cth = np.cos(theta)
    if abs(cth) < 1e-8:
        phi = 0.0
        psi = np.arctan2(-R[0, 1], R[1, 1])
    else:
        phi = np.arctan2(R[2, 1], R[2, 2])
        psi = np.arctan2(R[1, 0], R[0, 0])
    return np.array([phi, theta, psi], dtype=float)


def attitude_planner(acc_cmd: np.ndarray, yaw_des: float, params: dict) -> np.ndarray:
    """Convert desired acceleration command into desired Euler angles.

    Uses a thrust-vector construction to account for tilt coupling.
    """

    g = float(params["gravity"])
    a = np.asarray(acc_cmd, dtype=float).reshape(3)

    tvec = a + np.array([0.0, 0.0, g], dtype=float)
    n = float(np.linalg.norm(tvec))
    if n < 1e-8:
        # Degenerate; fall back to level.
        return np.array([0.0, 0.0, float(yaw_des)], dtype=float)

    b3 = tvec / n

    b1d = np.array([np.cos(yaw_des), np.sin(yaw_des), 0.0], dtype=float)
    b2 = np.cross(b3, b1d)
    nb2 = float(np.linalg.norm(b2))
    if nb2 < 1e-8:
        b2 = np.array([0.0, 1.0, 0.0], dtype=float)
    else:
        b2 = b2 / nb2

    b1 = np.cross(b2, b3)
    R = np.column_stack((b1, b2, b3))

    eul = _rotmat_to_euler_zyx(R)
    eul[2] = float(yaw_des)
    return eul


def attitude_controller(
    current_state: np.ndarray,
    desired_rot: np.ndarray,
    desired_omega: np.ndarray,
    params: dict,
    integral: Dict[str, np.ndarray],
    kp: np.ndarray,
    ki: np.ndarray,
    kd: np.ndarray,
) -> np.ndarray:
    dt = 1.0 / float(params["sample_rate"])

    rot = current_state[6:9]
    omega = current_state[9:12]

    kp = np.asarray(kp, dtype=float).reshape(3)
    ki = np.asarray(ki, dtype=float).reshape(3)
    kd = np.asarray(kd, dtype=float).reshape(3)

    e = np.asarray(desired_rot, dtype=float).reshape(3) - rot
    # Wrap yaw error to [-pi, pi]
    e[2] = (e[2] + np.pi) % (2 * np.pi) - np.pi

    integral["e"] = integral["e"] + e * dt

    I = np.diag(np.asarray(params["inertia"], dtype=float).reshape(3))
    desired_omega = np.asarray(desired_omega, dtype=float).reshape(3)

    M = I @ (kp * e + ki * integral["e"] + kd * (desired_omega - omega))
    return M
