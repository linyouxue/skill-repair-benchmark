import numpy as np

from position_controller import position_controller, make_position_integral
from attitude_planner import attitude_planner
from attitude_controller import attitude_controller, make_attitude_integral
from motor_model import motor_model, thrust_moment_from_rpm
from dynamics import dynamics


def _hover_rpm(params: dict) -> float:
    m = float(params['mass'])
    g = float(params['gravity'])
    cT = float(params['thrust_coefficient'])
    F = m * g
    return float(np.sqrt((F / 4.0) / cT))


def simulate_trajectory(params: dict, planned: np.ndarray):
    planned = np.array(planned, dtype=float)
    max_iter = planned.shape[1]
    dt = 1.0 / float(params['sample_rate'])

    state = np.zeros(16, dtype=float)
    state[0:3] = planned[0:3, 0]
    state[3:6] = planned[3:6, 0]
    state[6:9] = planned[6:9, 0]
    state[9:12] = planned[9:12, 0]

    rpm0 = _hover_rpm(params)
    state[12:16] = rpm0

    actual = np.zeros((15, max_iter), dtype=float)

    pos_int = make_position_integral()
    att_int = make_attitude_integral()

    rot_des_prev = state[6:9].copy()


    for k in range(max_iter):
        actual[0:3, k] = state[0:3]
        actual[3:6, k] = state[3:6]
        actual[6:9, k] = state[6:9]
        actual[9:12, k] = state[9:12]

        if k == 0:
            actual[12:15, k] = planned[12:15, 0]
        else:
            F_now, _M_now = thrust_moment_from_rpm(params, state[12:16])
            sdot = dynamics(params, state, F_now, np.zeros(3))
            actual[12:15, k] = sdot[3:6]

        if k == max_iter - 1:
            break

        des_pos = planned[0:3, k]
        des_vel = planned[3:6, k]
        des_acc = planned[12:15, k]
        yaw_des = float(planned[8, k])
        yaw_rate_des = float(planned[11, k])

        _F_cmd, acc_cmd = position_controller(
            current_pos=state[0:3],
            current_vel=state[3:6],
            desired_pos=des_pos,
            desired_vel=des_vel,
            desired_acc=des_acc,
            params=params,
            integral=pos_int,
        )

        g = float(params['gravity'])
        F_cmd = float(params['mass']) * float(np.linalg.norm(acc_cmd + np.array([0.0, 0.0, g])))
        rot_des, _omega_tmp = attitude_planner(acc_cmd, yaw_des, yaw_rate_des, gravity=g)
        rot_dot_des = (rot_des - rot_des_prev) / dt
        rot_des_prev = rot_des
        omega_des = np.array([rot_dot_des[0], rot_dot_des[1], yaw_rate_des], dtype=float)

        M_cmd = attitude_controller(
            current_rot=state[6:9],
            current_omega=state[9:12],
            desired_rot=rot_des,
            desired_omega=omega_des,
            params=params,
            integral=att_int,
        )

        _rpm_des, rpm_dot = motor_model(params, F_cmd, M_cmd, state[12:16])
        state[12:16] = np.clip(state[12:16] + rpm_dot * dt, float(params['rpm_min']), float(params['rpm_max']))

        F_act, M_act = thrust_moment_from_rpm(params, state[12:16])
        sdot = dynamics(params, state, F_act, M_act)
        state[0:12] = state[0:12] + sdot[0:12] * dt

    return actual
