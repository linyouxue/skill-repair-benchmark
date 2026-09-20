"""Offline PID tuning: grid-search gains, write tuning_results.yaml."""

import copy
import itertools
import pandas as pd
import yaml

from acc_system import AdaptiveCruiseControl


def rise_time(times, values, target):
    t10 = t90 = None
    for t, v in zip(times, values):
        if t10 is None and v >= 0.1 * target:
            t10 = t
        if t90 is None and v >= 0.9 * target:
            t90 = t
            break
    if t10 is not None and t90 is not None:
        return t90 - t10
    return None


def overshoot_percent(values, target):
    m = max(values)
    return 0.0 if m <= target else (m - target) / target * 100


def steady_state_error(values, target, frac=0.1):
    n = len(values)
    tail = values[int(n * (1 - frac)):]
    return abs(target - sum(tail) / len(tail))


def simulate(config, sensor_df):
    dt = config['simulation']['dt']
    mx, mn = config['vehicle']['max_acceleration'], config['vehicle']['max_deceleration']
    acc = AdaptiveCruiseControl(config)
    ego = 0.0
    sim_d = None
    prev_present = False
    times, speeds, dists, derrs, modes = [], [], [], [], []
    for _, row in sensor_df.iterrows():
        ls = None if pd.isna(row['lead_speed']) else float(row['lead_speed'])
        sd = None if pd.isna(row['distance']) else float(row['distance'])
        present = ls is not None and sd is not None
        if present and not prev_present:
            sim_d = sd
        if not present:
            sim_d = None
        prev_present = present
        a, mode, derr = acc.compute(ego, ls, sim_d, dt)
        times.append(row['time'])
        speeds.append(ego)
        dists.append(sim_d)
        derrs.append(derr)
        modes.append(mode)
        a = max(mn, min(mx, a))
        ego = max(0.0, ego + a * dt)
        if sim_d is not None and ls is not None:
            sim_d = sim_d + (ls - ego) * dt
    return times, speeds, dists, derrs, modes


def score_speed(times, speeds, target, cruise_end_time=30.0):
    # only evaluate during the initial cruise phase
    t_arr = [t for t in times if t <= cruise_end_time]
    s_arr = speeds[:len(t_arr)]
    rt = rise_time(t_arr, s_arr, target)
    ov = overshoot_percent(s_arr, target)
    sse = steady_state_error(s_arr, target, frac=0.2)
    return rt, ov, sse


def score_distance(times, modes, derrs, lead_speeds, set_speed=30.0):
    """Score distance steady-state error during quasi-steady follow window.

    Only evaluate when in follow mode AND lead_speed is below set_speed so
    ACC can actually match speed (otherwise ego is speed-capped and distance
    grows unavoidably).
    """
    window = []
    for t, m, de, ls in zip(times, modes, derrs, lead_speeds):
        if m == 'follow' and de is not None and ls is not None and ls < set_speed - 1.0:
            if 40.0 <= t <= 70.0:  # quasi-steady window
                window.append(de)
    if not window:
        return None
    n = len(window)
    tail = window[int(n * 0.5):]
    return abs(sum(tail) / len(tail))


def main():
    with open('vehicle_params.yaml') as f:
        base = yaml.safe_load(f)
    sensor_df = pd.read_csv('sensor_data.csv')
    target = base['acc_settings']['set_speed']

    # --- Tune speed PID (uses cruise phase 0..30s) ---
    best_speed = None
    speed_grid = list(itertools.product(
        [0.5, 0.8, 1.0, 1.5, 2.0],   # kp
        [0.0, 0.05, 0.1, 0.2],        # ki
        [0.0, 0.1, 0.2, 0.5],         # kd
    ))
    for kp, ki, kd in speed_grid:
        cfg = copy.deepcopy(base)
        cfg['pid_speed'] = {'kp': kp, 'ki': ki, 'kd': kd}
        # distance PID doesn't matter here; use placeholder
        cfg['pid_distance'] = {'kp': 0.3, 'ki': 0.02, 'kd': 0.1}
        times, speeds, _, _, _ = simulate(cfg, sensor_df)
        rt, ov, sse = score_speed(times, speeds, target)
        if rt is None or rt >= 10 or ov >= 5 or sse >= 0.5:
            continue
        # Prefer low overshoot then low sse then fast rise
        key = (ov, sse, rt)
        if best_speed is None or key < best_speed[0]:
            best_speed = (key, (kp, ki, kd), (rt, ov, sse))

    if best_speed is None:
        raise RuntimeError("No speed PID gains met the targets")
    (rt, ov, sse), speed_gains = best_speed[2], best_speed[1]
    print(f"Speed PID: kp={speed_gains[0]} ki={speed_gains[1]} kd={speed_gains[2]} "
          f"-> rise={rt:.2f}s overshoot={ov:.2f}% sse={sse:.3f}")

    # --- Tune distance PID using the best speed gains ---
    best_dist = None
    dist_grid = list(itertools.product(
        [0.2, 0.3, 0.5, 0.8, 1.0, 1.5],
        [0.0, 0.02, 0.05, 0.1],
        [0.0, 0.1, 0.2, 0.5],
    ))
    for kp, ki, kd in dist_grid:
        cfg = copy.deepcopy(base)
        cfg['pid_speed'] = {'kp': speed_gains[0], 'ki': speed_gains[1], 'kd': speed_gains[2]}
        cfg['pid_distance'] = {'kp': kp, 'ki': ki, 'kd': kd}
        times, speeds, dists, derrs, modes = simulate(cfg, sensor_df)
        lead_speeds = [None if pd.isna(x) else float(x) for x in sensor_df['lead_speed']]
        dsse = score_distance(times, modes, derrs, lead_speeds)
        if dsse is None:
            continue
        actual_dists = [d for d, m in zip(dists, modes) if m != 'cruise' and d is not None]
        min_d = min(actual_dists) if actual_dists else float('inf')
        if dsse >= 2.0 or min_d <= 5.0:
            continue
        key = (dsse, -min_d)
        if best_dist is None or key < best_dist[0]:
            best_dist = (key, (kp, ki, kd), (dsse, min_d))

    if best_dist is None:
        raise RuntimeError("No distance PID gains met the targets")
    (dsse, min_d), dist_gains = best_dist[2], best_dist[1]
    print(f"Dist  PID: kp={dist_gains[0]} ki={dist_gains[1]} kd={dist_gains[2]} "
          f"-> sse={dsse:.3f} min_dist={min_d:.2f}")

    out = {
        'pid_speed': {'kp': float(speed_gains[0]), 'ki': float(speed_gains[1]), 'kd': float(speed_gains[2])},
        'pid_distance': {'kp': float(dist_gains[0]), 'ki': float(dist_gains[1]), 'kd': float(dist_gains[2])},
    }
    with open('tuning_results.yaml', 'w') as f:
        yaml.dump(out, f, default_flow_style=False, sort_keys=False)
    print("Wrote tuning_results.yaml")


if __name__ == '__main__':
    main()
