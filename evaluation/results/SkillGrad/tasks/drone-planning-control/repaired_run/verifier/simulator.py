from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from controllers import Gains, attitude_controller, attitude_planner, make_attitude_integral, make_position_integral, position_controller
from dynamics import dynamics
from motor_model import motor_model


@dataclass
class SimulationResult:
    actual: np.ndarray  # (15, N)
    internal_state: np.ndarray  # (16, N)


def simulate_closed_loop(traj_des: np.ndarray, params: dict, gains: Gains) -> SimulationResult:
    dt = float(params["dt"])
    cT = float(params["thrust_coefficient"])
    rpm_min = float(params["rpm_min"])
    rpm_max = float(params["rpm_max"])

    N = int(traj_des.shape[1])

    # Internal state: pos, vel, euler, omega, motor rpm
    s = np.zeros(16, dtype=float)
    s[0:3] = traj_des[0:3, 0]
    s[3:6] = traj_des[3:6, 0]
    s[6:9] = traj_des[6:9, 0]
    s[9:12] = traj_des[9:12, 0]

    # Initialize motors near hover.
    rpm_hover = np.sqrt(float(params["mass"]) * float(params["gravity"]) / (4.0 * cT))
    rpm_hover = float(np.clip(rpm_hover, rpm_min, rpm_max))
    s[12:16] = rpm_hover

    actual = np.zeros((15, N), dtype=float)
    internal = np.zeros((16, N), dtype=float)

    pos_int = make_position_integral()
    att_int = make_attitude_integral()

    last_acc = np.zeros(3, dtype=float)

    for k in range(N - 1):
        desired = traj_des[:, k]

        cur_pos = s[0:3]
        cur_vel = s[3:6]
        cur_rot = s[6:9]
        cur_omega = s[9:12]
        cur_rpm = s[12:16]

        F_des, acc_cmd = position_controller(
            current_pos=cur_pos,
            current_vel=cur_vel,
            desired_pos=desired[0:3],
            desired_vel=desired[3:6],
            desired_acc=desired[12:15],
            params=params,
            gains=gains,
            integral=pos_int,
        )

        yaw_des = float(desired[8])
        rot_des, omega_des = attitude_planner(acc_cmd, yaw_des=yaw_des, gravity=float(params["gravity"]))

        M_des = attitude_controller(
            current_rot=cur_rot,
            current_omega=cur_omega,
            desired_rot=rot_des,
            desired_omega=omega_des,
            params=params,
            gains=gains,
            integral=att_int,
        )

        u = np.array([F_des, M_des[0], M_des[1], M_des[2]], dtype=float)
        F_act, M_act, rpm_dot, _rpm_des = motor_model(params, u, cur_rpm)

        sd = dynamics(params, s, F_act, M_act, rpm_dot)
        last_acc = sd[3:6].copy()

        actual[0:3, k] = cur_pos
        actual[3:6, k] = cur_vel
        actual[6:9, k] = cur_rot
        actual[9:12, k] = cur_omega
        actual[12:15, k] = last_acc

        internal[:, k] = s

        s = s + dt * sd
        s[12:16] = np.clip(s[12:16], rpm_min, rpm_max)

    # final sample
    actual[0:3, -1] = s[0:3]
    actual[3:6, -1] = s[3:6]
    actual[6:9, -1] = s[6:9]
    actual[9:12, -1] = s[9:12]
    actual[12:15, -1] = last_acc
    internal[:, -1] = s

    return SimulationResult(actual=actual, internal_state=internal)
