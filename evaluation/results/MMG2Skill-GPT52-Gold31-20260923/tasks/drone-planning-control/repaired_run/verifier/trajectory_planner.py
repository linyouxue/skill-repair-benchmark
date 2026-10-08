from __future__ import annotations

from typing import List, Tuple

import numpy as np
import yaml


def _min_jerk_profile(s: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Rest-to-rest minimum-jerk profile for s in [0, 1].

    Returns unitless (pos, vel, acc) wrt s.
    Time scaling is done by the caller.
    """

    s2 = s * s
    s3 = s2 * s
    s4 = s3 * s
    s5 = s4 * s

    pos = 10.0 * s3 - 15.0 * s4 + 6.0 * s5
    vel = 30.0 * s2 - 60.0 * s3 + 30.0 * s4
    acc = 60.0 * s - 180.0 * s2 + 120.0 * s3
    return pos, vel, acc


def _segment_eval_min_jerk(
    x0: np.ndarray,
    x1: np.ndarray,
    t0: float,
    t1: float,
    t: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Evaluate a vector min-jerk segment between x0 and x1."""

    T = float(t1 - t0)
    if T <= 0:
        raise ValueError("Non-positive segment duration")

    s = (t - t0) / T
    s = np.clip(s, 0.0, 1.0)
    pf, vf, af = _min_jerk_profile(s)

    x0 = np.asarray(x0, dtype=float).reshape(-1, 1)
    x1 = np.asarray(x1, dtype=float).reshape(-1, 1)
    dx = x1 - x0

    pos = x0 + dx * pf.reshape(1, -1)
    vel = dx * (vf.reshape(1, -1) / T)
    acc = dx * (af.reshape(1, -1) / (T * T))
    return pos, vel, acc


def _enforce_accel_limits(acc: np.ndarray) -> np.ndarray:
    """Clip (3, N) acceleration to physical limits from system_params.yaml."""

    params = yaml.safe_load(open("/root/system_params.yaml"))
    up = float(params["accel_limit_up"])
    down = float(params["accel_limit_down"])
    horiz = float(params["accel_limit_horiz"])

    acc = acc.copy()
    acc[2, :] = np.clip(acc[2, :], -down, up)

    axy = acc[0:2, :]
    norms = np.linalg.norm(axy, axis=0)
    scale = np.ones_like(norms)
    mask = norms > horiz
    scale[mask] = horiz / norms[mask]
    acc[0, :] *= scale
    acc[1, :] *= scale
    return acc


def _attitude_from_accel(acc: np.ndarray, yaw: np.ndarray, g: float) -> np.ndarray:
    ax = acc[0, :]
    ay = acc[1, :]
    psi = yaw

    phi = (ax * np.sin(psi) - ay * np.cos(psi)) / g
    theta = (ax * np.cos(psi) + ay * np.sin(psi)) / g
    return np.vstack([phi, theta, psi])


def trajectory_planner(
    waypoints: np.ndarray,
    max_iter: int,
    waypoint_times: np.ndarray,
    sample_rate: float,
    modes: List[str],
) -> np.ndarray:
    """Generate desired state matrix (15 x max_iter) for a flight plan."""

    if waypoints.shape[0] != 4:
        raise ValueError("waypoints must be shaped (4, n)")
    if waypoints.shape[1] != waypoint_times.shape[0]:
        raise ValueError("waypoints and waypoint_times mismatch")
    if waypoints.shape[1] - 1 != len(modes):
        raise ValueError("modes length must be n-1")

    dt = 1.0 / float(sample_rate)
    t = np.arange(max_iter, dtype=float) * dt

    pos = np.zeros((3, max_iter), dtype=float)
    vel = np.zeros((3, max_iter), dtype=float)
    acc = np.zeros((3, max_iter), dtype=float)
    yaw = np.zeros((max_iter,), dtype=float)

    for i, mode in enumerate(modes):
        t0 = float(waypoint_times[i])
        t1 = float(waypoint_times[i + 1])
        mask = (t >= t0) & (t <= t1 + 1e-12)
        if not np.any(mask):
            continue

        p0 = waypoints[0:3, i]
        p1 = waypoints[0:3, i + 1]
        y0 = float(waypoints[3, i])
        y1 = float(waypoints[3, i + 1])
        tt = t[mask]

        if mode.lower() == "hover":
            pos[:, mask] = p0.reshape(3, 1)
            vel[:, mask] = 0.0
            acc[:, mask] = 0.0
            yaw[mask] = y0
            continue

        p_seg, v_seg, a_seg = _segment_eval_min_jerk(p0, p1, t0, t1, tt)
        y_seg, ydot_seg, _ = _segment_eval_min_jerk(
            np.array([y0]), np.array([y1]), t0, t1, tt
        )

        pos[:, mask] = p_seg
        vel[:, mask] = v_seg
        acc[:, mask] = a_seg
        yaw[mask] = y_seg.reshape(-1)

    # If max_iter extends past last time, hold final pose.
    time_final = float(waypoint_times[-1])
    after = t > time_final
    if np.any(after):
        last_idx = int(np.max(np.where(t <= time_final)[0]))
        pos[:, after] = pos[:, last_idx].reshape(3, 1)
        vel[:, after] = 0.0
        acc[:, after] = 0.0
        yaw[after] = yaw[last_idx]

    acc = _enforce_accel_limits(acc)

    params = yaml.safe_load(open("/root/system_params.yaml"))
    g = float(params["gravity"])

    rot = _attitude_from_accel(acc, yaw, g)

    omega = np.zeros((3, max_iter), dtype=float)
    if max_iter >= 2:
        omega[:, 1:] = (rot[:, 1:] - rot[:, :-1]) / dt
        omega[:, 0] = omega[:, 1]

    traj = np.zeros((15, max_iter), dtype=float)
    traj[0:3, :] = pos
    traj[3:6, :] = vel
    traj[6:9, :] = rot
    traj[9:12, :] = omega
    traj[12:15, :] = acc
    return traj
