import numpy as np


def make_attitude_integral():
    return {'e': np.zeros(3, dtype=float)}


def attitude_controller(current_rot: np.ndarray, current_omega: np.ndarray,
                        desired_rot: np.ndarray, desired_omega: np.ndarray,
                        params: dict, integral: dict):
    dt = 1.0 / float(params['sample_rate'])

    e = desired_rot - current_rot
    integral['e'] = integral['e'] + e * dt

    kp = np.array(params['kp_att'], dtype=float)
    ki = np.array(params['ki_att'], dtype=float)
    kd = np.array(params['kd_att'], dtype=float)

    I = params['inertia_matrix']

    u = kp * e + ki * integral['e'] + kd * (desired_omega - current_omega)
    M = I @ u
    return M
