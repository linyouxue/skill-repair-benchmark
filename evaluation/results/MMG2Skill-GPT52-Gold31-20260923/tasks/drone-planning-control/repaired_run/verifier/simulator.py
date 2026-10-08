from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np

from controllers import (
    attitude_controller,
    attitude_planner,
    make_attitude_integral,
    make_position_integral,
    position_controller,
)
from motor_model import motor_model
from quad_dynamics import rk4_step, state16_to_state15


@dataclass
class Gains:
    kp_pos: np.ndarray
    ki_pos: np.ndarray
    kd_pos: np.ndarray
    kp_att: np.ndarray
    ki_att: np.ndarray
    kd_att: np.ndarray


def simulate(params: dict, desired_traj: np.ndarray, gains: Gains) -> np.ndarray:
    """Run simulation with PID outer + inner loop.

    Returns:
        actual_traj: (15, N)
    """

    desired_traj = np.asarray(desired_traj, dtype=float)
    N = int(desired_traj.shape[1])
    dt = 1.0 / float(params["sample_rate"])

    # Internal state: [pos, vel, euler, omega, motor_rpm]
    state16 = np.zeros((16,), dtype=float)
    state16[0:3] = desired_traj[0:3, 0]
    state16[3:6] = desired_traj[3:6, 0]
    state16[6:9] = desired_traj[6:9, 0]
    state16[9:12] = desired_traj[9:12, 0]
    # Start motors at hover RPM to avoid an artificial initial drop.
    cT = float(params["thrust_coefficient"])
    rpm_min = float(params["rpm_min"])
    rpm_max = float(params["rpm_max"])
    m = float(params["mass"])
    g = float(params["gravity"])
    rpm_hover = float(np.sqrt(max(m * g / (4.0 * cT), 0.0)))
    rpm_hover = float(np.clip(rpm_hover, rpm_min, rpm_max))
    state16[12:16] = rpm_hover

    pos_int = make_position_integral()
    att_int = make_attitude_integral()

    actual = np.zeros((15, N), dtype=float)

    rot_des_prev = None

    for k in range(N):
        current15 = np.zeros((15,), dtype=float)
        current15[0:3] = state16[0:3]
        current15[3:6] = state16[3:6]
        current15[6:9] = state16[6:9]
        current15[9:12] = state16[9:12]

        desired15 = desired_traj[:, k]

        F_des, acc_cmd = position_controller(
            current15,
            desired15,
            params,
            pos_int,
            gains.kp_pos,
            gains.ki_pos,
            gains.kd_pos,
        )

        yaw_des = float(desired15[8])
        rot_des = attitude_planner(acc_cmd, yaw_des, params)

        if rot_des_prev is None:
            rot_des_prev = rot_des.copy()
        rot_dot_des = (rot_des - rot_des_prev) / dt
        omega_des = np.array([rot_dot_des[0], rot_dot_des[1], float(desired15[11])], dtype=float)
        rot_des_prev = rot_des.copy()

        M_des = attitude_controller(
            current15,
            rot_des,
            omega_des,
            params,
            att_int,
            gains.kp_att,
            gains.ki_att,
            gains.kd_att,
        )

        # Log after applying controls to the current state.
        F_act, _, _ = motor_model(params, state16[12:16], F_des, M_des)
        actual[:, k] = state16_to_state15(params, state16, F_act)

        if k < N - 1:
            state16 = rk4_step(params, state16, dt, F_des, M_des)

    return actual
