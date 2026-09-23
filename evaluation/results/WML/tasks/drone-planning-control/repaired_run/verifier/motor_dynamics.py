from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np

from controllers import Gains, attitude_controller, attitude_planner, make_attitude_integral, make_position_integral, position_controller
from system_params import SystemParams


def motor_model(
    params: SystemParams,
    motor_rpm: np.ndarray,
    F_des: float,
    M_des: np.ndarray,
) -> Tuple[float, np.ndarray, np.ndarray]:
    """Map desired force/moments -> rpm setpoint, apply first-order lag.

    Returns actual (F, M) from current rpm, and rpm_dot to integrate.
    """
    motor_rpm = np.asarray(motor_rpm, dtype=float).reshape(4)
    cmd = np.array([F_des, float(M_des[0]), float(M_des[1]), float(M_des[2])], dtype=float)

    # Desired squared RPMs.
    rpm_sq = np.linalg.solve(params.prop_matrix, cmd)
    rpm_sq = np.clip(rpm_sq, 0.0, None)
    rpm_des = np.sqrt(rpm_sq)
    rpm_des = np.clip(rpm_des, params.rpm_min, params.rpm_max)

    rpm_dot = params.motor_constant * (rpm_des - motor_rpm)

    fm = params.prop_matrix @ (motor_rpm**2)
    F_act = float(fm[0])
    M_act = fm[1:4]
    return F_act, M_act, rpm_dot


def _rotation_matrix(phi: float, theta: float, psi: float) -> np.ndarray:
    cphi, sphi = np.cos(phi), np.sin(phi)
    cth, sth = np.cos(theta), np.sin(theta)
    cpsi, spsi = np.cos(psi), np.sin(psi)

    # ZYX: Rz * Ry * Rx
    return np.array(
        [
            [cpsi * cth, cpsi * sth * sphi - spsi * cphi, cpsi * sth * cphi + spsi * sphi],
            [spsi * cth, spsi * sth * sphi + cpsi * cphi, spsi * sth * cphi - cpsi * sphi],
            [-sth, cth * sphi, cth * cphi],
        ],
        dtype=float,
    )


def dynamics(params: SystemParams, state: np.ndarray, F: float, M: np.ndarray, rpm_dot: np.ndarray) -> np.ndarray:
    s = np.asarray(state, dtype=float).reshape(16)

    pos = s[0:3]
    vel = s[3:6]
    rot = s[6:9]
    omega = s[9:12]

    phi, theta, psi = float(rot[0]), float(rot[1]), float(rot[2])

    R = _rotation_matrix(phi, theta, psi)
    acc_world = R @ np.array([0.0, 0.0, float(F) / params.mass], dtype=float) + np.array([0.0, 0.0, -params.gravity])

    rot_dot = omega
    omega_dot = params.inertia_inv @ np.asarray(M, dtype=float).reshape(3)

    sd = np.zeros(16, dtype=float)
    sd[0:3] = vel
    sd[3:6] = acc_world
    sd[6:9] = rot_dot
    sd[9:12] = omega_dot
    sd[12:16] = np.asarray(rpm_dot, dtype=float).reshape(4)
    return sd


@dataclass(frozen=True)
class SimResult:
    planned: np.ndarray  # (15,n)
    actual: np.ndarray  # (15,n)
    time: np.ndarray  # (n,)
    max_pos_error: float


def _initial_motor_rpm_hover(params: SystemParams) -> float:
    rpm = np.sqrt((params.mass * params.gravity / 4.0) / params.thrust_coefficient)
    return float(np.clip(rpm, params.rpm_min, params.rpm_max))


def simulate_trajectory(planned: np.ndarray, params: SystemParams, gains: Gains) -> SimResult:
    planned = np.asarray(planned, dtype=float)
    n = planned.shape[1]

    dt = params.dt
    t = dt * np.arange(n)

    # State: [pos(3), vel(3), rot(3), omega(3), motor_rpm(4)]
    s = np.zeros(16, dtype=float)
    s[0:3] = planned[0:3, 0]
    s[3:6] = planned[3:6, 0]
    s[6:9] = planned[6:9, 0]
    s[9:12] = planned[9:12, 0]
    s[12:16] = _initial_motor_rpm_hover(params)

    pos_int = make_position_integral()
    att_int = make_attitude_integral()

    pos_hist = np.zeros((3, n), dtype=float)
    vel_hist = np.zeros((3, n), dtype=float)
    rot_hist = np.zeros((3, n), dtype=float)
    omg_hist = np.zeros((3, n), dtype=float)

    pos_hist[:, 0] = s[0:3]
    vel_hist[:, 0] = s[3:6]
    rot_hist[:, 0] = s[6:9]
    omg_hist[:, 0] = s[9:12]

    for k in range(n - 1):
        desired_pos = planned[0:3, k]
        desired_vel = planned[3:6, k]
        desired_rot = planned[6:9, k]
        desired_omega = planned[9:12, k]
        desired_acc = planned[12:15, k]

        cur_pos = s[0:3]
        cur_vel = s[3:6]
        cur_rot = s[6:9]
        cur_omega = s[9:12]

        F_des, acc_cmd = position_controller(
            cur_pos,
            cur_vel,
            desired_pos,
            desired_vel,
            desired_acc,
            params,
            gains,
            pos_int,
        )

        # Plan attitude based on commanded acceleration, but use planned yaw.
        rot_cmd = attitude_planner(acc_cmd, float(desired_rot[2]), params)

        M_des = attitude_controller(
            cur_rot,
            cur_omega,
            rot_cmd,
            desired_omega,
            params,
            gains,
            att_int,
        )

        F_act, M_act, rpm_dot = motor_model(params, s[12:16], F_des, M_des)

        # Integrate one timestep with a fixed-step RK4 (inputs held constant over dt).
        f = lambda y: dynamics(params, y, F_act, M_act, rpm_dot)
        k1 = f(s)
        k2 = f(s + 0.5 * dt * k1)
        k3 = f(s + 0.5 * dt * k2)
        k4 = f(s + dt * k3)
        s = s + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)

        pos_hist[:, k + 1] = s[0:3]
        vel_hist[:, k + 1] = s[3:6]
        rot_hist[:, k + 1] = s[6:9]
        omg_hist[:, k + 1] = s[9:12]

    acc_hist = np.zeros((3, n), dtype=float)
    acc_hist[:, :-1] = (vel_hist[:, 1:] - vel_hist[:, :-1]) / dt
    acc_hist[:, -1] = acc_hist[:, -2] if n > 1 else 0.0

    actual = np.zeros((15, n), dtype=float)
    actual[0:3, :] = pos_hist
    actual[3:6, :] = vel_hist
    actual[6:9, :] = rot_hist
    actual[9:12, :] = omg_hist
    actual[12:15, :] = acc_hist

    pos_err = np.linalg.norm(actual[0:3, :].T - planned[0:3, :].T, axis=1)

    return SimResult(
        planned=planned,
        actual=actual,
        time=t,
        max_pos_error=float(np.max(pos_err)),
    )
