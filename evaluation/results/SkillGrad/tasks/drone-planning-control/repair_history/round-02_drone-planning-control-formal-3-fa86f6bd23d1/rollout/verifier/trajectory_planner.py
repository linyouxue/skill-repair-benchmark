from __future__ import annotations

import numpy as np

from controllers import attitude_planner
from utils import DesiredState


def _min_jerk(s: np.ndarray):
    p = 10 * s**3 - 15 * s**4 + 6 * s**5
    v = 30 * s**2 - 60 * s**3 + 30 * s**4
    a = 60 * s - 180 * s**2 + 120 * s**3
    return p, v, a


def trajectory_planner(
    waypoints: np.ndarray,
    waypoint_times: np.ndarray,
    sample_rate: float,
    modes: list[str],
    params: dict,
):
    waypoints = np.asarray(waypoints, dtype=float)
    waypoint_times = np.asarray(waypoint_times, dtype=float)

    dt = 1.0 / float(sample_rate)
    nseg = waypoints.shape[1] - 1

    pieces: list[np.ndarray] = []
    for i in range(nseg):
        t0, t1 = float(waypoint_times[i]), float(waypoint_times[i + 1])
        T = t1 - t0
        steps = max(1, int(round(T * sample_rate)))

        p0 = waypoints[:, i]
        p1 = waypoints[:, i + 1]

        s = (np.arange(steps, dtype=float) * dt) / T
        s = np.clip(s, 0.0, 1.0)
        mj_p, mj_v, mj_a = _min_jerk(s)

        seg = np.zeros((15, steps), dtype=float)

        for ax in range(3):
            d = p1[ax] - p0[ax]
            seg[ax, :] = p0[ax] + d * mj_p
            seg[3 + ax, :] = (d / T) * mj_v
            seg[12 + ax, :] = (d / (T**2)) * mj_a

        seg[8, :] = p0[3] + (p1[3] - p0[3]) * mj_p
        pieces.append(seg)

    last = np.zeros((15, 1), dtype=float)
    last[0:3, 0] = waypoints[0:3, -1]
    last[8, 0] = waypoints[3, -1]
    pieces.append(last)

    traj = np.concatenate(pieces, axis=1)

    accel_lim_h = float(params['accel_limit_horiz'])
    accel_lim_up = float(params['accel_limit_up'])
    accel_lim_dn = float(params['accel_limit_down'])

    for k in range(traj.shape[1]):
        axy = traj[12:14, k]
        n = float(np.linalg.norm(axy))
        if n > accel_lim_h and n > 1e-12:
            traj[12:14, k] = axy * (accel_lim_h / n)
        traj[14, k] = float(np.clip(traj[14, k], -accel_lim_dn, accel_lim_up))

    for k in range(traj.shape[1]):
        desired = DesiredState(
            pos=traj[0:3, k],
            vel=traj[3:6, k],
            rot=np.array([0.0, 0.0, traj[8, k]], dtype=float),
            omega=np.zeros(3, dtype=float),
            acc=traj[12:15, k],
        )
        rot, omega = attitude_planner(desired, params)
        traj[6:9, k] = rot
        traj[9:12, k] = omega

    return traj
