import numpy as np


def make_position_integral():
    return {"e": np.zeros(3)}


def make_attitude_integral():
    return {"e": np.zeros(3)}


def position_controller(current_pos, current_vel,
                        desired_pos, desired_vel, desired_acc,
                        params, integral):
    kp = np.asarray(params['kp_pos'])
    ki = np.asarray(params['ki_pos'])
    kd = np.asarray(params['kd_pos'])
    dt = 1.0 / params['sample_rate']
    mass = params['mass']
    g = params['gravity']

    pos_err = current_pos - desired_pos
    vel_err = current_vel - desired_vel
    integral['e'] += pos_err * dt

    acc_cmd = desired_acc - kp * pos_err - ki * integral['e'] - kd * vel_err

    # clamp to physical limits
    az = np.clip(acc_cmd[2], -params['accel_limit_down'], params['accel_limit_up'])
    axy_norm = np.hypot(acc_cmd[0], acc_cmd[1])
    if axy_norm > params['accel_limit_horiz']:
        scale = params['accel_limit_horiz'] / axy_norm
        acc_cmd[0] *= scale
        acc_cmd[1] *= scale
    acc_cmd[2] = az

    F = mass * (g + acc_cmd[2])
    return F, acc_cmd


def attitude_planner(desired_acc, desired_yaw, desired_yaw_rate, params):
    g = params['gravity']
    ax, ay = desired_acc[0], desired_acc[1]
    psi = desired_yaw
    # inverse kinematics: small-angle approximation
    phi_des   = ( ax * np.sin(psi) - ay * np.cos(psi)) / g
    theta_des = ( ax * np.cos(psi) + ay * np.sin(psi)) / g

    # clamp to sensible angle range
    max_tilt = np.deg2rad(35.0)
    phi_des   = np.clip(phi_des,   -max_tilt, max_tilt)
    theta_des = np.clip(theta_des, -max_tilt, max_tilt)

    rot   = np.array([phi_des, theta_des, psi])
    omega = np.array([0.0, 0.0, desired_yaw_rate])
    return rot, omega


def attitude_controller(current_rot, current_omega,
                        desired_rot, desired_omega,
                        params, integral):
    kp = np.asarray(params['kp_att'])
    ki = np.asarray(params['ki_att'])
    kd = np.asarray(params['kd_att'])
    dt = 1.0 / params['sample_rate']
    I  = np.diag(params['inertia'])

    e = desired_rot - current_rot
    # wrap yaw error to [-pi, pi]
    e[2] = (e[2] + np.pi) % (2 * np.pi) - np.pi
    integral['e'] += e * dt

    ang = kp * e + ki * integral['e'] + kd * (desired_omega - current_omega)
    M = I @ ang
    return M
