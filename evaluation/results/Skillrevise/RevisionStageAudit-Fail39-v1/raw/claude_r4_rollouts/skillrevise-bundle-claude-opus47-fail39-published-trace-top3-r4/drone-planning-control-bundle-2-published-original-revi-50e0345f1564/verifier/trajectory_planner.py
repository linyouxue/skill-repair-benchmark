"""Trajectory planner: produces (15 x max_iter) desired state matrix.

Uses a C2-continuous quintic time scaling s(tau) = 10 tau^3 - 15 tau^4 + 6 tau^5,
which gives zero velocity and zero acceleration at both ends — bounded jerk.
"""

import numpy as np


def _quintic(tau):
    # tau in [0, 1]
    s = 10 * tau ** 3 - 15 * tau ** 4 + 6 * tau ** 5
    sd = 30 * tau ** 2 - 60 * tau ** 3 + 30 * tau ** 4
    sdd = 60 * tau - 180 * tau ** 2 + 120 * tau ** 3
    return s, sd, sdd


def plan_trajectory(waypoints, waypoint_times, modes, sample_rate):
    """Return (planned_state[15, N], time_vec[N])."""
    dt = 1.0 / sample_rate
    t_final = float(waypoint_times[-1])
    N = int(round(t_final * sample_rate)) + 1
    time_vec = np.arange(N) * dt

    state = np.zeros((15, N))

    for seg_idx, mode in enumerate(modes):
        t0 = waypoint_times[seg_idx]
        t1 = waypoint_times[seg_idx + 1]
        p0 = waypoints[0:3, seg_idx]
        p1 = waypoints[0:3, seg_idx + 1]
        yaw0 = waypoints[3, seg_idx]
        yaw1 = waypoints[3, seg_idx + 1]
        T = t1 - t0

        k0 = int(round(t0 * sample_rate))
        k1 = int(round(t1 * sample_rate))
        # inclusive on left of each segment; on last segment include final sample
        if seg_idx == len(modes) - 1:
            k_end = k1 + 1
        else:
            k_end = k1

        for k in range(k0, k_end):
            if k >= N:
                break
            t = k * dt
            tau = (t - t0) / T if T > 0 else 1.0
            tau = min(max(tau, 0.0), 1.0)

            if mode == 'hover':
                pos = p0
                vel = np.zeros(3)
                acc = np.zeros(3)
                yaw = yaw0
            else:
                s, sd, sdd = _quintic(tau)
                pos = p0 + (p1 - p0) * s
                vel = (p1 - p0) * sd / T
                acc = (p1 - p0) * sdd / T ** 2
                yaw = yaw0 + (yaw1 - yaw0) * s

            state[0:3, k] = pos
            state[3:6, k] = vel
            state[6:9, k] = [0.0, 0.0, yaw]  # desired roll/pitch filled by attitude planner
            state[9:12, k] = 0.0
            state[12:15, k] = acc

    return state, time_vec


def check_acceleration_limits(planned_state, params):
    """Return (ok, max_up, max_down, max_horiz)."""
    acc = planned_state[12:15, :]
    max_up = float(np.max(acc[2]))
    max_down = float(-np.min(acc[2]))
    max_horiz = float(np.max(np.sqrt(acc[0] ** 2 + acc[1] ** 2)))

    ok = (
        max_up < params['accel_limit_up']
        and max_down < params['accel_limit_down']
        and max_horiz < params['accel_limit_horiz']
    )
    return ok, max_up, max_down, max_horiz
