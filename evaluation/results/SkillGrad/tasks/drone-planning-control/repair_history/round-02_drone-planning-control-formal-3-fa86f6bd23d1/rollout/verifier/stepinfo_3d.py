from __future__ import annotations

import numpy as np


def stepinfo_3d(
    pos_actual: np.ndarray,
    pos_target: np.ndarray,
    t: np.ndarray,
    settling_threshold: float = 0.02,
):
    pos_actual = np.asarray(pos_actual, dtype=float)
    pos_target = np.asarray(pos_target, dtype=float).reshape(3)
    t = np.asarray(t, dtype=float)

    dist = np.linalg.norm(pos_actual.T - pos_target[None, :], axis=1)
    d0 = float(dist[0])

    if d0 < 1e-6:
        return {
            'RiseTime': 0.0,
            'SettlingTime': 0.0,
            'Overshoot_pct': 0.0,
            'SteadyStateError': float(dist[-1]),
        }

    rise_time = float(t[-1])
    for k in range(len(t)):
        if dist[k] <= 0.1 * d0:
            rise_time = float(t[k])
            break

    settle_band = settling_threshold * d0
    settling_time = 0.0
    for k in range(len(t) - 1, -1, -1):
        if dist[k] > settle_band:
            settling_time = float(t[k])
            break

    entry_idx = None
    for k in range(len(t)):
        if dist[k] <= settle_band:
            entry_idx = k
            break

    overshoot = 0.0
    if entry_idx is not None:
        max_post = float(np.max(dist[entry_idx:]))
        overshoot = (max_post / d0) * 100.0

    return {
        'RiseTime': float(rise_time),
        'SettlingTime': float(settling_time),
        'Overshoot_pct': float(overshoot),
        'SteadyStateError': float(dist[-1]),
    }
