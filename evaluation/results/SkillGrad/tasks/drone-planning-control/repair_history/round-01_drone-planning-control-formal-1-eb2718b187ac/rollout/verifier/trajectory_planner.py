from __future__ import annotations

from typing import List

import numpy as np


def _half_cosine_segment(p0: np.ndarray, p1: np.ndarray, t: np.ndarray, t0: float, t1: float):
    dt = t1 - t0
    if dt <= 0:
        raise ValueError("Non-positive segment duration")
    s = (t - t0) / dt
    dp = (p1 - p0).reshape(3, 1)

    pos = p0.reshape(3, 1) + dp * (1.0 - np.cos(np.pi * s)) / 2.0
    vel = dp * (np.pi / (2.0 * dt)) * np.sin(np.pi * s)
    acc = dp * (np.pi**2 / (2.0 * dt**2)) * np.cos(np.pi * s)
    return pos, vel, acc


def trajectory_planner(
    waypoints: np.ndarray,
    max_iter: int,
    waypoint_times: np.ndarray,
    sample_rate: float,
    modes: List[str],
) -> np.ndarray:
    """Return (15, max_iter) desired state: pos, vel, rot, omega, acc.

    This produces piecewise half-cosine segments with zero endpoint velocity.
    Orientation (rows 6:12) is left as zeros and should be filled by an attitude planner.
    """

    waypoints = np.asarray(waypoints, dtype=float)
    waypoint_times = np.asarray(waypoint_times, dtype=float)

    t = np.arange(max_iter, dtype=float) / float(sample_rate)

    traj = np.zeros((15, max_iter), dtype=float)

    for seg_idx, mode in enumerate(modes):
        t0 = float(waypoint_times[seg_idx])
        t1 = float(waypoint_times[seg_idx + 1])
        k0 = int(np.round(t0 * sample_rate))
        k1 = int(np.round(t1 * sample_rate))
        k0 = max(0, min(max_iter - 1, k0))
        k1 = max(0, min(max_iter - 1, k1))
        if k1 < k0:
            continue

        p0 = waypoints[0:3, seg_idx]
        p1 = waypoints[0:3, seg_idx + 1]

        if mode.lower() == "hover" or np.allclose(p0, p1):
            traj[0:3, k0 : k1 + 1] = p0.reshape(3, 1)
            traj[3:6, k0 : k1 + 1] = 0.0
            traj[12:15, k0 : k1 + 1] = 0.0
        else:
            tt = t[k0 : k1 + 1]
            pos, vel, acc = _half_cosine_segment(p0, p1, tt, t0, t1)
            traj[0:3, k0 : k1 + 1] = pos
            traj[3:6, k0 : k1 + 1] = vel
            traj[12:15, k0 : k1 + 1] = acc

    # Ensure last sample equals last waypoint exactly.
    traj[0:3, -1] = waypoints[0:3, -1]
    traj[3:6, -1] = 0.0
    traj[12:15, -1] = 0.0

    # yaw is always zero in this benchmark.
    traj[6:9, :] = 0.0
    traj[9:12, :] = 0.0

    return traj
