from __future__ import annotations

from typing import Dict

import numpy as np


def stepinfo_3d(
    pos_actual: np.ndarray,  # (3, N)
    pos_target: np.ndarray,  # (3,)
    t: np.ndarray,  # (N,)
    settling_threshold: float = 0.02,
) -> Dict[str, float]:
    pos_target = pos_target.reshape(3, 1)
    dist = np.linalg.norm(pos_actual - pos_target, axis=0)

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
    for k in range(dist.shape[0]):
        if float(dist[k]) <= rise_band:
            rise_time = float(t[k])
            break

    settle_band = settling_threshold * d0
    settling_time = 0.0
    for k in range(dist.shape[0] - 1, -1, -1):
        if float(dist[k]) > settle_band:
            settling_time = float(t[k])
            break

    entered_idx = None
    for k in range(dist.shape[0]):
        if float(dist[k]) <= settle_band:
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
