from __future__ import annotations

from typing import List, Tuple

import numpy as np


def _quintic_profile(p0: float, p1: float, t: np.ndarray, T: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Minimum-jerk quintic rest-to-rest trajectory for 1D motion."""
    if T <= 0:
        raise ValueError('Segment duration must be positive')

    s = np.clip(t / T, 0.0, 1.0)
    D = p1 - p0

    pos = p0 + D * (10 * s**3 - 15 * s**4 + 6 * s**5)
    vel = D / T * (30 * s**2 - 60 * s**3 + 30 * s**4)
    acc = D / (T**2) * (60 * s - 180 * s**2 + 120 * s**3)
    return pos, vel, acc


def _attitude_from_acc(acc_xy: np.ndarray, yaw: float, g: float) -> Tuple[float, float, float]:
    ax, ay = float(acc_xy[0]), float(acc_xy[1])
    phi = (ax * np.sin(yaw) - ay * np.cos(yaw)) / g
    theta = (ax * np.cos(yaw) + ay * np.sin(yaw)) / g
    return phi, theta, yaw


def trajectory_planner(
    waypoints: np.ndarray,
    max_iter: int,
    waypoint_times: np.ndarray,
    sample_rate: float,
    modes: List[str],
    gravity: float = 9.80665,
) -> np.ndarray:
    """Generate a (15 x max_iter) desired state matrix.

    Rows: 0:3 pos, 3:6 vel, 6:9 euler, 9:12 body rates, 12:15 accel.
    """

    if waypoints.shape[0] != 4:
        raise ValueError('waypoints must be (4,n)')
    if len(waypoint_times) != waypoints.shape[1]:
        raise ValueError('waypoint_times length mismatch')
    if len(modes) != waypoints.shape[1] - 1:
        raise ValueError('modes must be n-1')

    dt = 1.0 / float(sample_rate)
    t_vec = np.arange(max_iter) * dt

    traj = np.zeros((15, max_iter), dtype=float)

    for seg_i, mode in enumerate(modes):
        t0, t1 = float(waypoint_times[seg_i]), float(waypoint_times[seg_i + 1])
        if t1 <= t0:
            raise ValueError('Non-increasing waypoint times')

        idx = np.where((t_vec >= t0 - 1e-12) & (t_vec <= t1 + 1e-12))[0]
        t_local = t_vec[idx] - t0
        T = t1 - t0

        p0 = waypoints[0:3, seg_i]
        p1 = waypoints[0:3, seg_i + 1]
        yaw0 = float(waypoints[3, seg_i])
        yaw1 = float(waypoints[3, seg_i + 1])

        if mode.lower() == 'hover':
            pos = np.repeat(p1.reshape(3, 1), len(idx), axis=1)
            vel = np.zeros((3, len(idx)))
            acc = np.zeros((3, len(idx)))
            yaw = np.full((len(idx),), yaw1)
        else:
            pos = np.zeros((3, len(idx)))
            vel = np.zeros((3, len(idx)))
            acc = np.zeros((3, len(idx)))
            for ax_i in range(3):
                pos[ax_i], vel[ax_i], acc[ax_i] = _quintic_profile(
                    float(p0[ax_i]), float(p1[ax_i]), t_local, T
                )
            yaw = yaw0 + (yaw1 - yaw0) * np.clip(t_local / T, 0.0, 1.0)

        traj[0:3, idx] = pos
        traj[3:6, idx] = vel
        traj[12:15, idx] = acc

        for k, j in enumerate(idx):
            phi, theta, psi = _attitude_from_acc(acc[0:2, k], float(yaw[k]), gravity)
            traj[6:9, j] = [phi, theta, psi]
            traj[9:12, j] = [0.0, 0.0, 0.0]

    return traj
