from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

from system_params import SystemParams


@dataclass(frozen=True)
class PlannedTrajectory:
    state_des: np.ndarray  # (15, n)
    time: np.ndarray  # (n,)


def _min_jerk_1d(p0: float, p1: float, t: np.ndarray, T: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Minimum-jerk quintic with zero vel/acc at endpoints."""
    if T <= 0:
        raise ValueError("Segment duration must be positive")

    s = np.clip(t / T, 0.0, 1.0)

    # Position basis: 10 s^3 - 15 s^4 + 6 s^5
    pos = p0 + (p1 - p0) * (10 * s**3 - 15 * s**4 + 6 * s**5)

    # Derivatives w.r.t time.
    ds_dt = 1.0 / T
    vel = (p1 - p0) * (30 * s**2 - 60 * s**3 + 30 * s**4) * ds_dt

    acc = (p1 - p0) * (60 * s - 180 * s**2 + 120 * s**3) * (ds_dt**2)

    return pos, vel, acc


def _segment_samples(t0: float, t1: float, dt: float, *, include_start: bool) -> np.ndarray:
    if t1 < t0:
        raise ValueError("Non-monotonic segment time")
    n = int(np.round((t1 - t0) / dt))
    # Build explicit grid to avoid accumulating dt drift.
    base = t0 + dt * np.arange(n + 1, dtype=float)
    base[-1] = t1
    if include_start:
        return base
    return base[1:]


def trajectory_planner(
    waypoints: np.ndarray,
    max_iter: int,
    waypoint_times: np.ndarray,
    sample_rate: float,
    modes: List[str],
    params: SystemParams,
) -> np.ndarray:
    """Create a (15 x max_iter) planned trajectory for the whole flight plan."""
    dt = 1.0 / float(sample_rate)

    wps = np.asarray(waypoints, dtype=float)
    ts = np.asarray(waypoint_times, dtype=float)

    if wps.shape[0] != 4:
        raise ValueError("waypoints must be shape (4, n)")
    if ts.ndim != 1 or ts.shape[0] != wps.shape[1]:
        raise ValueError("waypoint_times must match waypoints")
    if len(modes) != wps.shape[1] - 1:
        raise ValueError("modes must have one entry per segment")

    t_final = float(ts[-1])
    n_expected = int(np.round(t_final * sample_rate)) + 1
    if max_iter != n_expected:
        # Caller might pass in; we still enforce the returned matrix size.
        max_iter = n_expected

    t_all: List[float] = []
    pos_all: List[np.ndarray] = []
    vel_all: List[np.ndarray] = []
    acc_all: List[np.ndarray] = []
    yaw_all: List[np.ndarray] = []

    for i, mode in enumerate(modes):
        t0 = float(ts[i])
        t1 = float(ts[i + 1])
        T = t1 - t0

        seg_t = _segment_samples(t0, t1, dt, include_start=(i == 0))
        tau = seg_t - t0

        p0 = wps[0:3, i]
        p1 = wps[0:3, i + 1]

        if mode == "hover":
            pos = np.repeat(p1.reshape(3, 1), seg_t.size, axis=1)
            vel = np.zeros_like(pos)
            acc = np.zeros_like(pos)
        else:
            pos = np.zeros((3, seg_t.size), dtype=float)
            vel = np.zeros_like(pos)
            acc = np.zeros_like(pos)
            for ax in range(3):
                pos[ax], vel[ax], acc[ax] = _min_jerk_1d(float(p0[ax]), float(p1[ax]), tau, T)

        yaw = np.repeat(float(wps[3, i + 1]), seg_t.size)

        t_all.append(seg_t)
        pos_all.append(pos)
        vel_all.append(vel)
        acc_all.append(acc)
        yaw_all.append(yaw)

    t_vec = np.concatenate(t_all)
    pos = np.concatenate(pos_all, axis=1)
    vel = np.concatenate(vel_all, axis=1)
    acc = np.concatenate(acc_all, axis=1)
    yaw = np.concatenate(yaw_all)

    if t_vec.size != max_iter:
        # Trim/pad conservatively.
        if t_vec.size > max_iter:
            t_vec = t_vec[:max_iter]
            pos = pos[:, :max_iter]
            vel = vel[:, :max_iter]
            acc = acc[:, :max_iter]
            yaw = yaw[:max_iter]
        else:
            pad = max_iter - t_vec.size
            t_vec = np.concatenate([t_vec, t_vec[-1] + dt * np.arange(1, pad + 1)])
            pos = np.concatenate([pos, np.repeat(pos[:, -1:], pad, axis=1)], axis=1)
            vel = np.concatenate([vel, np.zeros((3, pad))], axis=1)
            acc = np.concatenate([acc, np.zeros((3, pad))], axis=1)
            yaw = np.concatenate([yaw, np.repeat(yaw[-1], pad)])

    # Orientation from acceleration/yaw (small-angle inverse kinematics).
    phi = (acc[0] * np.sin(yaw) - acc[1] * np.cos(yaw)) / params.gravity
    theta = (acc[0] * np.cos(yaw) + acc[1] * np.sin(yaw)) / params.gravity
    rot = np.vstack([phi, theta, yaw])

    omega = np.zeros_like(rot)
    omega[:, :-1] = (rot[:, 1:] - rot[:, :-1]) * sample_rate
    omega[:, -1] = omega[:, -2] if omega.shape[1] > 1 else 0.0

    desired = np.zeros((15, max_iter), dtype=float)
    desired[0:3, :] = pos
    desired[3:6, :] = vel
    desired[6:9, :] = rot
    desired[9:12, :] = omega
    desired[12:15, :] = acc

    # Physical acceleration limit check for planned trajectory.
    az = desired[14, :]
    axy = np.linalg.norm(desired[12:14, :], axis=0)
    if np.any(az > params.accel_limit_up + 1e-6):
        raise ValueError("Planned trajectory violates accel_limit_up")
    if np.any(az < -params.accel_limit_down - 1e-6):
        raise ValueError("Planned trajectory violates accel_limit_down")
    if np.any(axy > params.accel_limit_horiz + 1e-6):
        raise ValueError("Planned trajectory violates accel_limit_horiz")

    return desired
