import numpy as np


def stepinfo_3d(pos_actual: np.ndarray, pos_target: np.ndarray, t: np.ndarray, settling_threshold: float = 0.02):
    pos_actual = np.array(pos_actual, dtype=float)
    pos_target = np.array(pos_target, dtype=float).reshape(3)
    t = np.array(t, dtype=float)

    dist = np.linalg.norm(pos_actual.T - pos_target.reshape(1, 3), axis=1)
    d0 = float(dist[0])
    if d0 < 1e-6:
        return {
            'RiseTime': 0.0,
            'SettlingTime': 0.0,
            'Overshoot_pct': 0.0,
            'SteadyStateError': float(dist[-1]),
        }

    rise_time = 0.0
    rise_thresh = 0.1 * d0
    for k in range(len(dist)):
        if dist[k] <= rise_thresh:
            rise_time = float(t[k])
            break

    band = settling_threshold * d0
    settling_time = 0.0
    for k in range(len(dist) - 1, -1, -1):
        if dist[k] > band:
            settling_time = float(t[k])
            break

    entered = np.where(dist <= band)[0]
    overshoot = 0.0
    if len(entered) > 0:
        first = int(entered[0])
        max_post = float(np.max(dist[first:]))
        overshoot = (max_post / d0) * 100.0

    return {
        'RiseTime': float(rise_time),
        'SettlingTime': float(settling_time),
        'Overshoot_pct': float(overshoot),
        'SteadyStateError': float(dist[-1]),
    }
