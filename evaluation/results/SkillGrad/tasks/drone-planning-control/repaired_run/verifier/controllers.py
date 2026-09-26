from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np

from rotations import wrap_angles


@dataclass
class Gains:
    kp_pos: np.ndarray
    ki_pos: np.ndarray
    kd_pos: np.ndarray
    kp_att: np.ndarray
    ki_att: np.ndarray
    kd_att: np.ndarray


def make_position_integral() -> Dict[str, np.ndarray]:
    return {"e": np.zeros(3, dtype=float)}


def make_attitude_integral() -> Dict[str, np.ndarray]:
    return {"e": np.zeros(3, dtype=float)}


def position_controller(
    current_pos: np.ndarray,
    current_vel: np.ndarray,
    desired_pos: np.ndarray,
    desired_vel: np.ndarray,
    desired_acc: np.ndarray,
    params: dict,
    gains: Gains,
    integral: Dict[str, np.ndarray],
) -> tuple[float, np.ndarray]:
    dt = float(params["dt"])
    mass = float(params["mass"])
    gravity = float(params["gravity"])

    pos_err = current_pos - desired_pos
    vel_err = current_vel - desired_vel

    integral["e"] = integral["e"] + pos_err * dt

    acc_cmd = desired_acc - gains.kp_pos * pos_err - gains.ki_pos * integral["e"] - gains.kd_pos * vel_err

    # thrust along body-z; we will compute orientation separately
    F = mass * (gravity + acc_cmd[2])
    return float(F), acc_cmd


def attitude_planner(acc_cmd: np.ndarray, yaw_des: float, gravity: float) -> tuple[np.ndarray, np.ndarray]:
    # Small-angle approximation around hover.
    ax, ay = float(acc_cmd[0]), float(acc_cmd[1])
    psi = float(yaw_des)

    phi_des = (ax * np.sin(psi) - ay * np.cos(psi)) / gravity
    theta_des = (ax * np.cos(psi) + ay * np.sin(psi)) / gravity

    rot_des = np.array([phi_des, theta_des, psi], dtype=float)
    omega_des = np.zeros(3, dtype=float)
    return rot_des, omega_des


def attitude_controller(
    current_rot: np.ndarray,
    current_omega: np.ndarray,
    desired_rot: np.ndarray,
    desired_omega: np.ndarray,
    params: dict,
    gains: Gains,
    integral: Dict[str, np.ndarray],
) -> np.ndarray:
    dt = float(params["dt"])
    I = params["inertia_matrix"]

    e = wrap_angles(desired_rot - current_rot)
    integral["e"] = integral["e"] + e * dt

    M = I @ (gains.kp_att * e + gains.ki_att * integral["e"] + gains.kd_att * (desired_omega - current_omega))
    return np.array(M, dtype=float)
