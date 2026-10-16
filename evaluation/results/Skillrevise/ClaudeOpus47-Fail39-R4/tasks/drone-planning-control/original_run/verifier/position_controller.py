import numpy as np


def make_position_integral():
    return {'e': np.zeros(3, dtype=float)}


def position_controller(current_pos: np.ndarray, current_vel: np.ndarray,
                        desired_pos: np.ndarray, desired_vel: np.ndarray, desired_acc: np.ndarray,
                        params: dict, integral: dict):
    dt = 1.0 / float(params['sample_rate'])

    pos_err = current_pos - desired_pos
    vel_err = current_vel - desired_vel

    integral['e'] = integral['e'] + pos_err * dt

    kp = np.array(params['kp_pos'], dtype=float)
    ki = np.array(params['ki_pos'], dtype=float)
    kd = np.array(params['kd_pos'], dtype=float)

    acc_cmd = desired_acc - kp * pos_err - ki * integral['e'] - kd * vel_err
    F_cmd = float(params['mass']) * (float(params['gravity']) + float(acc_cmd[2]))
    return F_cmd, acc_cmd
