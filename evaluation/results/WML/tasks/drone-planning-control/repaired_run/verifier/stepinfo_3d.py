from __future__ import annotations

from typing import Dict

import numpy as np


def stepinfo_3d(
    pos_actual: np.ndarray,
    pos_target: np.ndarray,
    t: np.ndarray,
    *,
    settling_threshold: float = 0.02,
) -> Dict[str, float]:
    """Compute step-response style metrics using 3D distance to target.

    Args:
        pos_actual: (3, n) actual positions.
        pos_target: (3,) target position.
        t: (n,) time vector.
        settling_threshold: fraction of initial distance defining the settling band.

    Returns:
        Dict with keys: RiseTime, SettlingTime, Overshoot_pct, SteadyStateError.
    """
    pos_actual = np.asarray(pos_actual, dtype=float)
    pos_target = np.asarray(pos_target, dtype=float).reshape(3)
    t = np.asarray(t, dtype=float)

    dist = np.linalg.norm(pos_actual.T - pos_target[None, :], axis=1)

    d0 = float(dist[0])
    if d0 < 1e-6:
        return {
            "RiseTime": 0.0,
            "SettlingTime": 0.0,
            "Overshoot_pct": 0.0,
            "SteadyStateError": float(dist[-1]),
        }

    rise_time = float(t[-1])
    rise_band = 0.1 * d0
    for k in range(len(t)):
        if dist[k] <= rise_band:
            rise_time = float(t[k])
            break

    settle_band = settling_threshold * d0
    settling_time = 0.0
    for k in range(len(t) - 1, -1, -1):
        if dist[k] > settle_band:
            settling_time = float(t[k])
            break

    entered = None
    for k in range(len(t)):
        if dist[k] <= settle_band:
            entered = k
            break

    if entered is None:
        overshoot_pct = 0.0
    else:
        max_post = float(np.max(dist[entered:]))
        overshoot_pct = max_post / d0 * 100.0

    return {
        "RiseTime": rise_time,
        "SettlingTime": settling_time,
        "Overshoot_pct": float(overshoot_pct),
        "SteadyStateError": float(dist[-1]),
    }
