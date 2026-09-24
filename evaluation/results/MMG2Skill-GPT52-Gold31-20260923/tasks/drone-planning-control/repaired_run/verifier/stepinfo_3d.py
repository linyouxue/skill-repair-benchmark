from __future__ import annotations

import numpy as np


def stepinfo_3d(
    pos_actual: np.ndarray,
    pos_target: np.ndarray,
    time_vec: np.ndarray,
    *,
    settling_threshold: float = 0.02,
) -> dict:
    """Compute 3D step-response metrics based on distance to target.

    Args:
        pos_actual: (3, n) actual positions.
        pos_target: (3,) target position.
        time_vec: (n,) time values in seconds.
        settling_threshold: fraction of initial distance defining settling band.

    Returns:
        dict with keys: RiseTime, SettlingTime, Overshoot_pct, SteadyStateError
    """

    pos_actual = np.asarray(pos_actual, dtype=float)
    pos_target = np.asarray(pos_target, dtype=float).reshape(3)
    time_vec = np.asarray(time_vec, dtype=float)

    if pos_actual.shape[0] != 3:
        raise ValueError("pos_actual must have shape (3, n)")

    dist = np.linalg.norm(pos_actual.T - pos_target[None, :], axis=1)
    d0 = float(dist[0])
    if d0 < 1e-6:
        return {
            "RiseTime": 0.0,
            "SettlingTime": 0.0,
            "Overshoot_pct": 0.0,
            "SteadyStateError": float(dist[-1]),
        }

    rise_time = float(time_vec[-1])
    for k in range(dist.shape[0]):
        if dist[k] <= 0.1 * d0:
            rise_time = float(time_vec[k])
            break

    band = settling_threshold * d0
    settling_time = 0.0
    for k in range(dist.shape[0] - 1, -1, -1):
        if dist[k] > band:
            settling_time = float(time_vec[k])
            break

    entered_idx = None
    for k in range(dist.shape[0]):
        if dist[k] <= band:
            entered_idx = k
            break

    overshoot_pct = 0.0
    if entered_idx is not None:
        max_post = float(np.max(dist[entered_idx:]))
        overshoot_pct = 100.0 * max_post / d0

    return {
        "RiseTime": float(rise_time),
        "SettlingTime": float(settling_time),
        "Overshoot_pct": float(overshoot_pct),
        "SteadyStateError": float(dist[-1]),
    }
