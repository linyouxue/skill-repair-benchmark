from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np

from system_params import SystemParams


def make_position_integral() -> Dict[str, np.ndarray]:
    return {"e": np.zeros(3, dtype=float)}


def make_attitude_integral() -> Dict[str, np.ndarray]:
    return {"e": np.zeros(3, dtype=float)}


@dataclass
class Gains:
    kp_pos: np.ndarray  # (3,)
    ki_pos: np.ndarray
    kd_pos: np.ndarray

    kp_att: np.ndarray
    ki_att: np.ndarray
    kd_att: np.ndarray


def position_controller(
    current_pos: np.ndarray,
    current_vel: np.ndarray,
    desired_pos: np.ndarray,
    desired_vel: np.ndarray,
    desired_acc: np.ndarray,
    params: SystemParams,
    gains: Gains,
    integral: Dict[str, np.ndarray],
) -> Tuple[float, np.ndarray]:
    dt = params.dt

    pos_err = current_pos - desired_pos
    vel_err = current_vel - desired_vel

    integral["e"] = integral["e"] + pos_err * dt

    acc_cmd = desired_acc - gains.kp_pos * pos_err - gains.ki_pos * integral["e"] - gains.kd_pos * vel_err

    F = params.mass * (params.gravity + acc_cmd[2])
    return float(F), acc_cmd


def attitude_planner(desired_acc: np.ndarray, yaw: float, params: SystemParams) -> np.ndarray:
    ax, ay = float(desired_acc[0]), float(desired_acc[1])
    g = params.gravity

    phi = (ax * np.sin(yaw) - ay * np.cos(yaw)) / g
    theta = (ax * np.cos(yaw) + ay * np.sin(yaw)) / g
    return np.array([phi, theta, yaw], dtype=float)


def attitude_controller(
    current_rot: np.ndarray,
    current_omega: np.ndarray,
    desired_rot: np.ndarray,
    desired_omega: np.ndarray,
    params: SystemParams,
    gains: Gains,
    integral: Dict[str, np.ndarray],
) -> np.ndarray:
    dt = params.dt

    e = desired_rot - current_rot
    integral["e"] = integral["e"] + e * dt

    u = gains.kp_att * e + gains.ki_att * integral["e"] + gains.kd_att * (desired_omega - current_omega)
    M = params.inertia @ u
    return M
