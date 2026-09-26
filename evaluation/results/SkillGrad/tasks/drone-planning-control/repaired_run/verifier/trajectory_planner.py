from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

from rotations import euler_from_rot_matrix


@dataclass
class Trajectory:
    state: np.ndarray  # (15, N)
    time: np.ndarray  # (N,)


def _min_jerk_profile(p0: np.ndarray, p1: np.ndarray, T: float, t: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    if T <= 0:
        raise ValueError("Segment duration must be positive")
    s = np.clip(t / T, 0.0, 1.0)

    h = 10 * s**3 - 15 * s**4 + 6 * s**5
    dh = (30 * s**2 - 60 * s**3 + 30 * s**4) / T
    ddh = (60 * s - 180 * s**2 + 120 * s**3) / (T**2)

    dp = (p1 - p0).reshape(3, 1)
    pos = p0.reshape(3, 1) + dp * h.reshape(1, -1)
    vel = dp * dh.reshape(1, -1)
    acc = dp * ddh.reshape(1, -1)
    return pos, vel, acc


def _orientation_from_acc(acc: np.ndarray, yaw: float, gravity: float) -> np.ndarray:
    # Desired body-z aligned with (a + g e3)
    a_vec = np.array([acc[0], acc[1], acc[2] + gravity], dtype=float)
    n = np.linalg.norm(a_vec)
    if n < 1e-9:
        return np.zeros(3)
    b3 = a_vec / n

    b1d = np.array([np.cos(yaw), np.sin(yaw), 0.0], dtype=float)
    b2 = np.cross(b3, b1d)
    b2n = np.linalg.norm(b2)
    if b2n < 1e-9:
        return np.zeros(3)
    b2 /= b2n
    b1 = np.cross(b2, b3)
    R = np.column_stack([b1, b2, b3])
    return euler_from_rot_matrix(R)


def _check_accel_limits(acc: np.ndarray, accel_limit_up: float, accel_limit_down: float, accel_limit_horiz: float) -> None:
    ax, ay, az = acc
    if np.sqrt(ax * ax + ay * ay) > accel_limit_horiz + 1e-9:
        raise ValueError("Planned trajectory exceeds horizontal acceleration limit")
    if az > accel_limit_up + 1e-9:
        raise ValueError("Planned trajectory exceeds upward acceleration limit")
    if az < -accel_limit_down - 1e-9:
        raise ValueError("Planned trajectory exceeds downward acceleration limit")


def trajectory_planner(
    waypoints: np.ndarray,
    waypoint_times: np.ndarray,
    sample_rate: float,
    modes: List[str],
    gravity: float,
    accel_limit_up: float,
    accel_limit_down: float,
    accel_limit_horiz: float,
) -> Trajectory:
    dt = 1.0 / float(sample_rate)
    t_final = float(waypoint_times[-1])
    N = int(np.round(t_final * sample_rate)) + 1
    time_vec = np.arange(N, dtype=float) * dt

    state = np.zeros((15, N), dtype=float)

    # Build segment by segment.
    idx0 = 0
    for seg_i, mode in enumerate(modes):
        t0 = float(waypoint_times[seg_i])
        t1 = float(waypoint_times[seg_i + 1])
        T = t1 - t0
        n_seg = int(np.round(T * sample_rate))
        if n_seg <= 0:
            continue

        # Segment time grid includes the start, excludes the end (except last seg)
        if seg_i == len(modes) - 1:
            t_local = np.arange(n_seg + 1, dtype=float) * dt
        else:
            t_local = np.arange(n_seg, dtype=float) * dt

        p0 = waypoints[0:3, seg_i]
        p1 = waypoints[0:3, seg_i + 1]
        yaw0 = float(waypoints[3, seg_i])
        yaw1 = float(waypoints[3, seg_i + 1])

        if mode == "hover":
            pos = np.repeat(p0.reshape(3, 1), t_local.size, axis=1)
            vel = np.zeros_like(pos)
            acc = np.zeros_like(pos)
            yaw = np.full((1, t_local.size), yaw0)
        else:
            pos, vel, acc = _min_jerk_profile(p0, p1, T, t_local)
            # simple yaw interpolation
            yaw = (yaw0 + (yaw1 - yaw0) * (t_local / max(T, 1e-9))).reshape(1, -1)

        j0 = int(np.round(t0 * sample_rate))
        j1 = j0 + pos.shape[1]

        state[0:3, j0:j1] = pos
        state[3:6, j0:j1] = vel
        state[12:15, j0:j1] = acc

        # Orientation from acceleration feedforward
        for k in range(j0, j1):
            _check_accel_limits(
                state[12:15, k],
                accel_limit_up=accel_limit_up,
                accel_limit_down=accel_limit_down,
                accel_limit_horiz=accel_limit_horiz,
            )
            rot = _orientation_from_acc(state[12:15, k], float(yaw[0, k - j0]), gravity)
            state[6:9, k] = rot
            state[9:12, k] = 0.0

        idx0 = j1

    # Fill any trailing samples (numerical rounding) with last waypoint state.
    if idx0 < N:
        state[:, idx0:] = state[:, idx0 - 1 : idx0]

    return Trajectory(state=state, time=time_vec)
