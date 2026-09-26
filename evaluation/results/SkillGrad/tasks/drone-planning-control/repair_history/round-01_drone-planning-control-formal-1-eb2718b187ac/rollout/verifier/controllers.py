from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np


@dataclass
class State:
    pos: np.ndarray  # (3,)
    vel: np.ndarray  # (3,)
    rot: np.ndarray  # (3,) euler [phi, theta, psi]
    omega: np.ndarray  # (3,) (treated as euler rates)


@dataclass
class DesiredState:
    pos: np.ndarray
    vel: np.ndarray
    rot: np.ndarray
    omega: np.ndarray
    acc: np.ndarray


def make_position_integral() -> Dict[str, np.ndarray]:
    return {"e": np.zeros(3, dtype=float)}


def make_attitude_integral() -> Dict[str, np.ndarray]:
    return {"e": np.zeros(3, dtype=float)}


def clamp_accel(params: dict, acc: np.ndarray) -> np.ndarray:
    acc = np.asarray(acc, dtype=float).copy()

    az_min = -float(params["accel_limit_down"])
    az_max = float(params["accel_limit_up"])
    acc[2] = float(np.clip(acc[2], az_min, az_max))

    axy = acc[0:2]
    norm_xy = float(np.linalg.norm(axy))
    axy_max = float(params["accel_limit_horiz"])
    if norm_xy > axy_max and norm_xy > 1e-9:
        acc[0:2] = axy * (axy_max / norm_xy)
    return acc


def position_controller(
    current: State,
    desired: DesiredState,
    params: dict,
    integral: Dict[str, np.ndarray],
    kp: np.ndarray,
    ki: np.ndarray,
    kd: np.ndarray,
) -> Tuple[float, np.ndarray]:
    dt = 1.0 / float(params["sample_rate"])

    pos_err = current.pos - desired.pos
    vel_err = current.vel - desired.vel

    integral["e"] = integral["e"] + pos_err * dt

    acc_cmd = desired.acc - kp * pos_err - ki * integral["e"] - kd * vel_err
    acc_cmd = clamp_accel(params, acc_cmd)

    m = float(params["mass"])
    g = float(params["gravity"])
    F = m * (g + acc_cmd[2])

    cT = float(params["thrust_coefficient"])
    rpm_min = float(params["rpm_min"])
    rpm_max = float(params["rpm_max"])
    T_min = 4.0 * cT * (rpm_min**2)
    T_max = 4.0 * cT * (rpm_max**2)
    F = float(np.clip(F, T_min, T_max))

    return F, acc_cmd


def attitude_planner(desired: DesiredState, params: dict) -> Tuple[np.ndarray, np.ndarray]:
    g = float(params["gravity"])
    ax, ay = float(desired.acc[0]), float(desired.acc[1])
    psi = float(desired.rot[2])

    phi_des = (ax * np.sin(psi) - ay * np.cos(psi)) / g
    theta_des = (ax * np.cos(psi) + ay * np.sin(psi)) / g

    rot = np.array([phi_des, theta_des, psi], dtype=float)
    omega = np.array([0.0, 0.0, float(desired.omega[2])], dtype=float)
    return rot, omega


def attitude_controller(
    current: State,
    desired: DesiredState,
    params: dict,
    integral: Dict[str, np.ndarray],
    kp: np.ndarray,
    ki: np.ndarray,
    kd: np.ndarray,
) -> np.ndarray:
    dt = 1.0 / float(params["sample_rate"])

    e = desired.rot - current.rot
    integral["e"] = integral["e"] + e * dt

    I = np.diag(np.asarray(params["inertia"], dtype=float))
    u = kp * e + ki * integral["e"] + kd * (desired.omega - current.omega)
    M = I @ u
    return M
