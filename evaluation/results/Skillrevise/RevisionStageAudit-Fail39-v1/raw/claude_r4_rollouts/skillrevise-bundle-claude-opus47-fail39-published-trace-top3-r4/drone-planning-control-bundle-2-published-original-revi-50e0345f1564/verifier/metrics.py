"""3D step-info metrics based on Euclidean distance to the final target."""

import numpy as np


def stepinfo_3d(pos_actual, pos_target, time_vec, settling_threshold=0.02):
    pos_actual = np.asarray(pos_actual)
    pos_target = np.asarray(pos_target).reshape(3)
    dist = np.linalg.norm(pos_actual - pos_target[:, None], axis=0)
    d0 = float(dist[0])

    if d0 < 1e-6:
        return {
            'RiseTime': 0.0,
            'SettlingTime': 0.0,
            'Overshoot_pct': 0.0,
            'SteadyStateError': float(dist[-1]),
        }

    rise_time = 0.0
    rise_thr = 0.1 * d0
    for k in range(len(dist)):
        if dist[k] <= rise_thr:
            rise_time = float(time_vec[k])
            break

    band = settling_threshold * d0
    settling_time = float(time_vec[-1])
    for k in range(len(dist) - 1, -1, -1):
        if dist[k] > band:
            settling_time = float(time_vec[k])
            break
    else:
        settling_time = 0.0

    overshoot_pct = 0.0
    entered = False
    for k in range(len(dist)):
        if not entered and dist[k] <= band:
            entered = True
            continue
        if entered and dist[k] > overshoot_pct:
            overshoot_pct = dist[k]
    overshoot_pct = float(overshoot_pct / d0 * 100.0) if entered else 0.0

    return {
        'RiseTime': float(rise_time),
        'SettlingTime': float(settling_time),
        'Overshoot_pct': float(overshoot_pct),
        'SteadyStateError': float(dist[-1]),
    }
