from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np

from math_utils import R_to_euler, clamp_vector_horiz, euler_to_R, wrap_pi
from params import SystemParams


@dataclass
class PIDGains:
    kp_pos: np.ndarray  # (3,)
    ki_pos: np.ndarray
    kd_pos: np.ndarray
    kp_att: np.ndarray  # (3,)
    ki_att: np.ndarray
    kd_att: np.ndarray


def make_position_integral() -> Dict[str, np.ndarray]:
    return {"e": np.zeros(3, dtype=float)}


def make_attitude_integral() -> Dict[str, np.ndarray]:
    return {"e": np.zeros(3, dtype=float)}


def attitude_planner_from_accel(a_cmd_world: np.ndarray, yaw_des: float, params: SystemParams):
    g = params.gravity
    e3 = np.array([0.0, 0.0, 1.0], dtype=float)
    a_total = a_cmd_world + g * e3
    norm_a = float(np.linalg.norm(a_total))
    if norm_a < 1e-9:
        b3 = e3
        thrust = 0.0
    else:
        b3 = a_total / norm_a
        thrust = params.mass * norm_a

    b1_yaw = np.array([np.cos(yaw_des), np.sin(yaw_des), 0.0], dtype=float)
    b2 = np.cross(b3, b1_yaw)
    n2 = float(np.linalg.norm(b2))
    if n2 < 1e-9:
        b2 = np.array([-np.sin(yaw_des), np.cos(yaw_des), 0.0], dtype=float)
    else:
        b2 = b2 / n2
    b1 = np.cross(b2, b3)

    R_des = np.column_stack([b1, b2, b3])
    euler_des = R_to_euler(R_des)
    euler_des[2] = yaw_des
    omega_des = np.zeros(3, dtype=float)
    return euler_des, omega_des, thrust


def position_controller(
    pos: np.ndarray,
    vel: np.ndarray,
    pos_des: np.ndarray,
    vel_des: np.ndarray,
    acc_des: np.ndarray,
    integral: Dict[str, np.ndarray],
    gains: PIDGains,
    params: SystemParams,
    dt: float,
) -> np.ndarray:
    e_p = pos_des - pos
    e_v = vel_des - vel
    integral["e"] = integral["e"] + e_p * dt

    a_cmd = acc_des + gains.kp_pos * e_p + gains.ki_pos * integral["e"] + gains.kd_pos * e_v

    a_cmd[2] = float(np.clip(a_cmd[2], -params.accel_limit_down, params.accel_limit_up))
    a_cmd[0:2] = clamp_vector_horiz(a_cmd[0:2], params.accel_limit_horiz)
    return a_cmd


def attitude_controller(
    euler: np.ndarray,
    omega_body: np.ndarray,
    euler_des: np.ndarray,
    omega_des: np.ndarray,
    integral: Dict[str, np.ndarray],
    gains: PIDGains,
    params: SystemParams,
    dt: float,
) -> np.ndarray:
    e = euler_des - euler
    e[2] = wrap_pi(float(e[2]))

    integral["e"] = integral["e"] + e * dt
    domega = omega_des - omega_body

    u = gains.kp_att * e + gains.ki_att * integral["e"] + gains.kd_att * domega
    return params.inertia @ u


def default_gains_for_mode(mode: str) -> PIDGains:
    if mode == "hover":
        kp_pos = np.array([10.0, 10.0, 14.0])
        kd_pos = np.array([6.0, 6.0, 9.0])
        ki_pos = np.array([0.05, 0.05, 0.1])
    elif mode in {"takeoff", "land"}:
        kp_pos = np.array([10.0, 10.0, 16.0])
        kd_pos = np.array([6.0, 6.0, 10.0])
        ki_pos = np.array([0.03, 0.03, 0.08])
    else:  # fly
        kp_pos = np.array([12.0, 12.0, 16.0])
        kd_pos = np.array([7.0, 7.0, 10.0])
        ki_pos = np.array([0.03, 0.03, 0.08])

    kp_att = np.array([220.0, 220.0, 140.0])
    kd_att = np.array([30.0, 30.0, 18.0])
    ki_att = np.array([0.0, 0.0, 0.5])

    return PIDGains(
        kp_pos=kp_pos,
        ki_pos=ki_pos,
        kd_pos=kd_pos,
        kp_att=kp_att,
        ki_att=ki_att,
        kd_att=kd_att,
    )
