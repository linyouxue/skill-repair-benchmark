import numpy as np

from controllers import (
    attitude_controller,
    attitude_planner,
    make_attitude_integral,
    make_position_integral,
    position_controller,
)
from motor_dynamics import build_prop_matrix, rk4_step


def simulate_trajectory(
    desired: np.ndarray,
    params: dict,
    gains: dict,
) -> tuple[np.ndarray, np.ndarray, dict]:
    desired = np.asarray(desired, dtype=float)
    max_iter = int(desired.shape[1])
    dt = float(params["dt"])

    prop_matrix = build_prop_matrix(params)

    m = float(params["mass"])
    g = float(params["gravity"])
    cT = float(params["thrust_coefficient"])

    rpm_hover = np.sqrt(max(m * g / (4.0 * cT), 0.0))
    rpm_hover = float(np.clip(rpm_hover, float(params["rpm_min"]), float(params["rpm_max"])))

    state = np.zeros(16, dtype=float)
    state[0:3] = desired[0:3, 0]
    state[3:6] = desired[3:6, 0]
    state[6:9] = desired[6:9, 0]
    state[9:12] = desired[9:12, 0]
    state[12:16] = rpm_hover

    actual = np.zeros((15, max_iter), dtype=float)
    time_vec = np.arange(max_iter, dtype=float) * dt

    pos_int = make_position_integral()
    att_int = make_attitude_integral()

    rot_des_prev = None

    for k in range(max_iter - 1):
        cur_pos = state[0:3]
        cur_vel = state[3:6]
        cur_rot = state[6:9]
        cur_omega = state[9:12]

        des_pos = desired[0:3, k]
        des_vel = desired[3:6, k]
        des_rot_plan = desired[6:9, k]
        des_omega_plan = desired[9:12, k]
        des_acc = desired[12:15, k]

        F_cmd, acc_cmd = position_controller(
            cur_pos,
            cur_vel,
            des_pos,
            des_vel,
            des_acc,
            params,
            gains,
            pos_int,
        )

        rot_des, _ = attitude_planner(acc_cmd, float(des_rot_plan[2]), params)

        if rot_des_prev is None:
            rot_dot_des = np.zeros(3, dtype=float)
        else:
            rot_dot_des = (rot_des - rot_des_prev) / dt
        rot_des_prev = rot_des

        omega_des = np.array([rot_dot_des[0], rot_dot_des[1], des_omega_plan[2]], dtype=float)

        M_cmd = attitude_controller(
            cur_rot,
            cur_omega,
            rot_des,
            omega_des,
            params,
            gains,
            att_int,
        )

        state_next, acc_world = rk4_step(state, F_cmd, M_cmd, params, prop_matrix)

        actual[0:3, k] = cur_pos
        actual[3:6, k] = cur_vel
        actual[6:9, k] = cur_rot
        actual[9:12, k] = cur_omega
        actual[12:15, k] = acc_world

        state = state_next

    actual[0:3, -1] = state[0:3]
    actual[3:6, -1] = state[3:6]
    actual[6:9, -1] = state[6:9]
    actual[9:12, -1] = state[9:12]
    actual[12:15, -1] = actual[12:15, -2]

    pos_err = np.linalg.norm((actual[0:3, :] - desired[0:3, :]).T, axis=1)
    summary = {
        "max_pos_error": float(np.max(pos_err)),
        "rms_pos_error": float(np.sqrt(np.mean(pos_err**2))),
    }

    return actual, time_vec, summary
