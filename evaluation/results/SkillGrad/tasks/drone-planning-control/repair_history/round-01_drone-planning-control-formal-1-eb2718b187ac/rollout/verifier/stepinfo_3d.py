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
    pos_actual = np.asarray(pos_actual, dtype=float)
    pos_target = np.asarray(pos_target, dtype=float).reshape(3)
    t = np.asarray(t, dtype=float)

    dist = np.linalg.norm(pos_actual.T - pos_target.reshape(1, 3), axis=1)
    if dist.size == 0 or dist[0] < 1e-6:
        return {
            "RiseTime": 0.0,
            "SettlingTime": 0.0,
            "Overshoot_pct": 0.0,
            "SteadyStateError": float(dist[-1]) if dist.size else 0.0,
        }

    d0 = float(dist[0])

    rise_time = 0.0
    rise_idx = None
    for k in range(dist.size):
        if dist[k] <= 0.1 * d0:
            rise_time = float(t[k])
            rise_idx = k
            break

    settling_time = 0.0
    for k in range(dist.size - 1, -1, -1):
        if dist[k] > settling_threshold * d0:
            settling_time = float(t[k])
            break

    overshoot_pct = 0.0
    if rise_idx is not None:
        entry_idx = None
        for k in range(rise_idx, dist.size):
            if dist[k] <= settling_threshold * d0:
                entry_idx = k
                break
        if entry_idx is not None:
            max_post = float(np.max(dist[entry_idx:]))
            overshoot_pct = max_post / d0 * 100.0

    return {
        "RiseTime": float(rise_time),
        "SettlingTime": float(settling_time),
        "Overshoot_pct": float(overshoot_pct),
        "SteadyStateError": float(dist[-1]),
    }
