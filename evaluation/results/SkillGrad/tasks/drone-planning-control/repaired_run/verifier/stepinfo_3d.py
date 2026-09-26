from __future__ import annotations

import numpy as np


def stepinfo_3d(pos_actual: np.ndarray, pos_target: np.ndarray, t: np.ndarray, settling_threshold: float = 0.02) -> dict:
    pos_actual = np.array(pos_actual, dtype=float)
    pos_target = np.array(pos_target, dtype=float).reshape(3)
    t = np.array(t, dtype=float).reshape(-1)

    dist = np.linalg.norm(pos_actual.T - pos_target.reshape(1, 3), axis=1)
    d0 = float(dist[0])
    if d0 < 1e-6:
        return {
            "RiseTime": 0.0,
            "SettlingTime": 0.0,
            "Overshoot_pct": 0.0,
            "SteadyStateError": float(dist[-1]),
        }

    rise_time = 0.0
    rise_idx = None
    for k in range(dist.size):
        if dist[k] <= 0.1 * d0:
            rise_time = float(t[k])
            rise_idx = k
            break

    band = settling_threshold * d0
    settling_time = float(t[-1])
    for k in range(dist.size - 1, -1, -1):
        if dist[k] > band:
            settling_time = float(t[k])
            break

    overshoot = 0.0
    entry_idx = None
    for k in range(dist.size):
        if dist[k] <= band:
            entry_idx = k
            break

    if entry_idx is not None:
        max_post = float(np.max(dist[entry_idx:]))
        overshoot = max_post / d0 * 100.0

    return {
        "RiseTime": rise_time,
        "SettlingTime": settling_time,
        "Overshoot_pct": float(overshoot),
        "SteadyStateError": float(dist[-1]),
    }
