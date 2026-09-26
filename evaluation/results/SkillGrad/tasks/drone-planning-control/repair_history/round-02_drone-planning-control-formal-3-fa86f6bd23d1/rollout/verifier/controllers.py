from __future__ import annotations

import numpy as np

from utils import CurrentState, DesiredState, clamp_norm_2d, wrap_angle_pi


def position_controller(
    current: CurrentState,
    desired: DesiredState,
    params: dict,
    integral: dict[str, np.ndarray],
):
    dt = 1.0 / float(params['sample_rate'])

    kp = np.asarray(params['kp_pos'], dtype=float)
    ki = np.asarray(params['ki_pos'], dtype=float)
    kd = np.asarray(params['kd_pos'], dtype=float)

    pos_err = current.pos - desired.pos
    vel_err = current.vel - desired.vel

    integral['e'] = integral['e'] + pos_err * dt

    acc_cmd = desired.acc - kp * pos_err - ki * integral['e'] - kd * vel_err

    acc_cmd[0:2] = clamp_norm_2d(acc_cmd[0:2], float(params['accel_limit_horiz']))
    acc_cmd[2] = float(
        np.clip(
            acc_cmd[2],
            -float(params['accel_limit_down']),
            float(params['accel_limit_up']),
        )
    )

    m = float(params['mass'])
    g = float(params['gravity'])

    F = m * (g + acc_cmd[2])
    F = float(np.clip(F, float(params['thrust_min']), float(params['thrust_max'])))

    acc_cmd[2] = (F / m) - g

    return F, acc_cmd


def attitude_planner(desired: DesiredState, params: dict):
    g = float(params['gravity'])
    ax, ay = float(desired.acc[0]), float(desired.acc[1])
    psi = float(desired.rot[2])

    phi = (ax * np.sin(psi) - ay * np.cos(psi)) / g
    theta = (ax * np.cos(psi) + ay * np.sin(psi)) / g

    max_tilt = float(params.get('max_tilt_rad', 0.6))
    phi = float(np.clip(phi, -max_tilt, max_tilt))
    theta = float(np.clip(theta, -max_tilt, max_tilt))

    rot = np.array([phi, theta, psi], dtype=float)
    omega = np.zeros(3, dtype=float)
    return rot, omega


def attitude_controller(
    current: CurrentState,
    desired: DesiredState,
    params: dict,
    integral: dict[str, np.ndarray],
):
    dt = 1.0 / float(params['sample_rate'])

    kp = np.asarray(params['kp_att'], dtype=float)
    ki = np.asarray(params['ki_att'], dtype=float)
    kd = np.asarray(params['kd_att'], dtype=float)

    e = desired.rot - current.rot
    e[2] = wrap_angle_pi(float(e[2]))

    integral['e'] = integral['e'] + e * dt

    I = np.asarray(params['inertia_matrix'], dtype=float)
    cmd = kp * e + ki * integral['e'] + kd * (desired.omega - current.omega)
    return I @ cmd
