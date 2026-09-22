import numpy as np

from controllers import attitude_planner


def min_jerk(p0: np.ndarray, p1: np.ndarray, T: float, t: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if T <= 1e-9:
        return p1.copy(), np.zeros_like(p0), np.zeros_like(p0)

    s = np.clip(t / T, 0.0, 1.0)
    s2, s3, s4, s5 = s * s, s * s * s, s**4, s**5

    pos = p0 + (p1 - p0) * (10.0 * s3 - 15.0 * s4 + 6.0 * s5)
    vel = (p1 - p0) * (30.0 * s2 - 60.0 * s3 + 30.0 * s4) / T
    acc = (p1 - p0) * (60.0 * s - 180.0 * s2 + 120.0 * s3) / (T * T)

    return pos, vel, acc


def _clip_acc(acc: np.ndarray, params: dict) -> np.ndarray:
    ax, ay, az = float(acc[0]), float(acc[1]), float(acc[2])

    az = float(np.clip(az, -float(params["accel_limit_down"]), float(params["accel_limit_up"])))

    axy = np.hypot(ax, ay)
    axy_lim = float(params["accel_limit_horiz"])
    if axy > axy_lim and axy > 1e-12:
        scale = axy_lim / axy
        ax *= scale
        ay *= scale

    return np.array([ax, ay, az], dtype=float)


def trajectory_planner(
    waypoints: np.ndarray,
    max_iter: int,
    waypoint_times: np.ndarray,
    sample_rate: float,
    modes: list[str],
    params: dict | None = None,
) -> np.ndarray:
    dt = 1.0 / float(sample_rate)
    time_vec = np.arange(max_iter, dtype=float) * dt

    traj = np.zeros((15, max_iter), dtype=float)

    pos = np.zeros((3, max_iter), dtype=float)
    vel = np.zeros((3, max_iter), dtype=float)
    acc = np.zeros((3, max_iter), dtype=float)
    yaw = np.zeros(max_iter, dtype=float)

    for k, t in enumerate(time_vec):
        if t >= float(waypoint_times[-1]):
            seg_idx = len(modes) - 1
            tau = float(waypoint_times[-1] - waypoint_times[-2])
            t0 = float(waypoint_times[-2])
            t1 = float(waypoint_times[-1])
            tau = t1 - t0
            local_t = tau
        else:
            seg_idx = int(np.searchsorted(waypoint_times, t, side="right") - 1)
            seg_idx = int(np.clip(seg_idx, 0, len(modes) - 1))
            t0 = float(waypoint_times[seg_idx])
            t1 = float(waypoint_times[seg_idx + 1])
            tau = t1 - t0
            local_t = t - t0

        p0 = waypoints[0:3, seg_idx]
        p1 = waypoints[0:3, seg_idx + 1]
        mode = modes[seg_idx]

        if mode == "hover":
            pos[:, k] = p0
            vel[:, k] = 0.0
            acc[:, k] = 0.0
        else:
            pos[:, k], vel[:, k], acc[:, k] = min_jerk(p0, p1, tau, local_t)

        yaw0 = float(waypoints[3, seg_idx])
        yaw1 = float(waypoints[3, seg_idx + 1])
        if abs(yaw1 - yaw0) < 1e-12 or tau <= 1e-12:
            yaw[k] = yaw0
        else:
            yaw[k] = yaw0 + (yaw1 - yaw0) * np.clip(local_t / tau, 0.0, 1.0)

    if params is not None:
        for k in range(max_iter):
            acc[:, k] = _clip_acc(acc[:, k], params)

    traj[0:3, :] = pos
    traj[3:6, :] = vel
    traj[12:15, :] = acc

    rot = np.zeros((3, max_iter), dtype=float)
    omega_des = np.zeros((3, max_iter), dtype=float)

    for k in range(max_iter):
        rot[:, k], _ = attitude_planner(acc[:, k], yaw[k], params or {"gravity": 9.80665})
        rot[2, k] = yaw[k]

    omega_des[:, 0] = 0.0
    for k in range(1, max_iter):
        omega_des[:, k] = (rot[:, k] - rot[:, k - 1]) / dt

    traj[6:9, :] = rot
    traj[9:12, :] = omega_des

    return traj
