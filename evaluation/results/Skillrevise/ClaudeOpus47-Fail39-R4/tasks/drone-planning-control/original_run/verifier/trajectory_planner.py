import numpy as np

from attitude_planner import attitude_planner


def _quintic_profile(p0: float, p1: float, t0: float, t1: float, t: float):
    T = float(t1 - t0)
    if T <= 0:
        return float(p1), 0.0, 0.0

    s = float((t - t0) / T)
    s = min(1.0, max(0.0, s))

    dp = float(p1 - p0)

    # Minimum-jerk / quintic time-scaling with zero vel/acc at endpoints:
    # p = p0 + dp*(10s^3 - 15s^4 + 6s^5)
    # v = dp*(30s^2 - 60s^3 + 30s^4)/T
    # a = dp*(60s - 180s^2 + 120s^3)/T^2
    s2 = s * s
    s3 = s2 * s
    s4 = s3 * s
    s5 = s4 * s

    p = p0 + dp * (10.0 * s3 - 15.0 * s4 + 6.0 * s5)
    v = dp * (30.0 * s2 - 60.0 * s3 + 30.0 * s4) / T
    a = dp * (60.0 * s - 180.0 * s2 + 120.0 * s3) / (T * T)

    return float(p), float(v), float(a)


def trajectory_planner(waypoints: np.ndarray, max_iter: int, waypoint_times: np.ndarray, sample_rate: float, modes):
    waypoints = np.array(waypoints, dtype=float)
    waypoint_times = np.array(waypoint_times, dtype=float)

    dt = 1.0 / float(sample_rate)
    n_wp = waypoints.shape[1]

    if n_wp < 2:
        raise ValueError('Need at least 2 waypoints')
    if len(modes) != n_wp - 1:
        raise ValueError('modes must have length n_waypoints - 1')

    t_vec = np.arange(max_iter, dtype=float) * dt
    traj = np.zeros((15, max_iter), dtype=float)

    for k, t in enumerate(t_vec):
        seg_idx = int(np.clip(np.searchsorted(waypoint_times, t, side='right') - 1, 0, n_wp - 2))
        t0, t1 = float(waypoint_times[seg_idx]), float(waypoint_times[seg_idx + 1])
        p0 = waypoints[:, seg_idx]
        p1 = waypoints[:, seg_idx + 1]
        mode = modes[seg_idx]

        if mode == 'hover':
            pos = p1[0:3]
            vel = np.zeros(3)
            acc = np.zeros(3)
            yaw = float(p1[3])
            yaw_rate = 0.0
        else:
            px, vx, ax = _quintic_profile(p0[0], p1[0], t0, t1, t)
            py, vy, ay = _quintic_profile(p0[1], p1[1], t0, t1, t)
            pz, vz, az = _quintic_profile(p0[2], p1[2], t0, t1, t)
            yaw, yaw_rate, _yaw_acc = _quintic_profile(p0[3], p1[3], t0, t1, t)

            pos = np.array([px, py, pz], dtype=float)
            vel = np.array([vx, vy, vz], dtype=float)
            acc = np.array([ax, ay, az], dtype=float)

        rot, _omega = attitude_planner(acc, yaw, yaw_rate, gravity=9.80665)

        traj[0:3, k] = pos
        traj[3:6, k] = vel
        traj[6:9, k] = rot
        traj[12:15, k] = acc

    # Numerical derivative for Euler angle rates (used as angular velocity proxy).
    rot = traj[6:9, :]
    omega = np.zeros_like(rot)
    if max_iter >= 2:
        omega[:, 0] = (rot[:, 1] - rot[:, 0]) / dt
        omega[:, -1] = (rot[:, -1] - rot[:, -2]) / dt
    if max_iter >= 3:
        omega[:, 1:-1] = (rot[:, 2:] - rot[:, :-2]) / (2.0 * dt)

    traj[9:12, :] = omega

    return traj
