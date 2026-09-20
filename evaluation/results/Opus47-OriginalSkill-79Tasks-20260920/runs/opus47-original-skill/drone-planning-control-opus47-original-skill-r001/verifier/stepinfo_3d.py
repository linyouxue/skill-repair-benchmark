import numpy as np


def stepinfo_3d(pos_actual, pos_target, t, settling_threshold=0.02):
    """
    Compute step-response metrics from 3D distance-to-target trajectory.
    pos_actual: (3, n); pos_target: (3,); t: (n,)
    """
    pos_actual = np.asarray(pos_actual)
    pos_target = np.asarray(pos_target).reshape(3, 1)
    dist = np.linalg.norm(pos_actual - pos_target, axis=0)
    t = np.asarray(t)
    n = len(t)

    d0 = dist[0]
    if d0 < 1e-6:
        return {
            'RiseTime': 0.0,
            'SettlingTime': 0.0,
            'Overshoot_pct': 0.0,
            'SteadyStateError': float(dist[-1]),
        }

    # rise time — first index where dist ≤ 10 % of initial
    rise_time = 0.0
    for k in range(n):
        if dist[k] <= 0.1 * d0:
            rise_time = float(t[k])
            break

    # settling time — last index outside settling band
    band = settling_threshold * d0
    settling_time = float(t[-1])
    for k in range(n - 1, -1, -1):
        if dist[k] > band:
            settling_time = float(t[k])
            break
    else:
        settling_time = 0.0

    # overshoot — max distance after first entering the band
    overshoot = 0.0
    entered = False
    for k in range(n):
        if not entered and dist[k] <= band:
            entered = True
            continue
        if entered:
            if dist[k] > overshoot:
                overshoot = dist[k]
    overshoot_pct = float(overshoot / d0 * 100.0) if entered else 0.0

    return {
        'RiseTime': float(rise_time),
        'SettlingTime': float(settling_time),
        'Overshoot_pct': overshoot_pct,
        'SteadyStateError': float(dist[-1]),
    }
