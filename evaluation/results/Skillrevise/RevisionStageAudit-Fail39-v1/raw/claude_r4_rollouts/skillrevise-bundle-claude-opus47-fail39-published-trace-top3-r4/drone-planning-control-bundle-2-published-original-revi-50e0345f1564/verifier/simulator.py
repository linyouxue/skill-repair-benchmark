"""Run the closed-loop simulation for a single flight plan."""

import numpy as np

from controllers import PositionPID, AttitudePID, attitude_planner, thrust_magnitude
from motor_dynamics import build_prop_matrix, motor_model, integrate_step


def simulate(planned_state, time_vec, params, pid_gains, initial_pos):
    """Run the full closed loop; return actual_state (15, N)."""
    dt = 1.0 / params['sample_rate']
    N = planned_state.shape[1]

    pos_pid = PositionPID(pid_gains['kp_pos'], pid_gains['ki_pos'], pid_gains['kd_pos'], dt)
    att_pid = AttitudePID(pid_gains['kp_att'], pid_gains['ki_att'], pid_gains['kd_att'], dt,
                          params['inertia'])

    prop_matrix = build_prop_matrix(params)

    # 16-state: [pos(3), vel(3), euler(3), omega(3), rpm(4)]
    s = np.zeros(16)
    s[0:3] = initial_pos
    # start motors at hover rpm
    hover_rpm_sq = params['mass'] * params['gravity'] / (4 * params['thrust_coefficient'])
    hover_rpm = float(np.sqrt(hover_rpm_sq))
    s[12:16] = hover_rpm

    actual = np.zeros((15, N))

    for k in range(N):
        pos_des = planned_state[0:3, k]
        vel_des = planned_state[3:6, k]
        acc_ff = planned_state[12:15, k]
        yaw_des = planned_state[8, k]

        pos_cur = s[0:3]
        vel_cur = s[3:6]
        rot_cur = s[6:9]
        omega_cur = s[9:12]

        # Position loop → desired acceleration
        a_des = pos_pid(pos_des, vel_des, acc_ff, pos_cur, vel_cur)

        # Thrust magnitude (tilt-compensated)
        F = thrust_magnitude(a_des, params)

        # Desired attitude from desired lateral acc + yaw
        rot_des = attitude_planner(a_des, yaw_des, params)
        omega_des = np.zeros(3)

        # Attitude loop → body moments
        M = att_pid(rot_des, omega_des, rot_cur, omega_cur)

        # Record actual state BEFORE the step so sample k is current measurement
        actual[0:3, k] = pos_cur
        actual[3:6, k] = vel_cur
        actual[6:9, k] = rot_cur
        actual[9:12, k] = omega_cur

        # Motor model and integration
        F_actual, M_actual, rpm_dot = motor_model(F, M, s[12:16], prop_matrix, params)

        # Record actual acceleration (world frame) from F_actual
        phi, theta, psi = rot_cur
        cphi, sphi = np.cos(phi), np.sin(phi)
        cth, sth = np.cos(theta), np.sin(theta)
        cpsi, spsi = np.cos(psi), np.sin(psi)
        m_ = params['mass']
        g_ = params['gravity']
        ax = (F_actual / m_) * (cpsi * sth * cphi + spsi * sphi)
        ay = (F_actual / m_) * (spsi * sth * cphi - cpsi * sphi)
        az = -g_ + (F_actual / m_) * cth * cphi
        actual[12:15, k] = [ax, ay, az]

        if k == N - 1:
            break
        s = integrate_step(s, F_actual, M_actual, rpm_dot, params, dt)

    return actual
