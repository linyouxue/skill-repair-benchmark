from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np

from controllers import attitude_planner_from_accel
from params import SystemParams


@dataclass(frozen=True)
class PlannedTrajectory:
    mode: str
    time: np.ndarray  # (N,)
    state_des: np.ndarray  # (15, N)


def _quintic_1d(p0: float, pf: float, t: np.ndarray, T: float):
    dp = pf - p0
    a0 = p0
    a1 = 0.0
    a2 = 0.0
    a3 = 10.0 * dp / (T**3)
    a4 = -15.0 * dp / (T**4)
    a5 = 6.0 * dp / (T**5)

    pos = a0 + a3 * t**3 + a4 * t**4 + a5 * t**5
    vel = 3 * a3 * t**2 + 4 * a4 * t**3 + 5 * a5 * t**4
    acc = 6 * a3 * t + 12 * a4 * t**2 + 20 * a5 * t**3
    return pos, vel, acc


def _check_accel_limits(acc: np.ndarray, params: SystemParams) -> None:
    ax, ay, az = acc
    horiz = np.sqrt(ax**2 + ay**2)
    if np.any(horiz > params.accel_limit_horiz + 1e-9):
        raise ValueError("Planned horizontal acceleration exceeds accel_limit_horiz")
    if np.any(az > params.accel_limit_up + 1e-9):
        raise ValueError("Planned upward acceleration exceeds accel_limit_up")
    if np.any(-az > params.accel_limit_down + 1e-9):
        raise ValueError("Planned downward acceleration exceeds accel_limit_down")


def plan_point_to_point(
    mode: str,
    start_pos: np.ndarray,
    end_pos: np.ndarray,
    duration_s: float,
    params: SystemParams,
    yaw: float = 0.0,
) -> PlannedTrajectory:
    dt = 1.0 / params.sample_rate
    N = int(round(duration_s * params.sample_rate)) + 1
    t = np.arange(N, dtype=float) * dt

    state_des = np.zeros((15, N), dtype=float)

    if mode == "hover":
        state_des[0:3, :] = start_pos.reshape(3, 1)
        _check_accel_limits(state_des[12:15, :], params)
        return PlannedTrajectory(mode=mode, time=t, state_des=state_des)

    T = float(duration_s)
    for i in range(3):
        pos, vel, acc = _quintic_1d(float(start_pos[i]), float(end_pos[i]), t, T)
        state_des[i, :] = pos
        state_des[i + 3, :] = vel
        state_des[i + 12, :] = acc

    state_des[8, :] = yaw

    _check_accel_limits(state_des[12:15, :], params)

    for k in range(N):
        euler_des, omega_des, _ = attitude_planner_from_accel(state_des[12:15, k], yaw, params)
        state_des[6:9, k] = euler_des
        state_des[9:12, k] = omega_des

    return PlannedTrajectory(mode=mode, time=t, state_des=state_des)
