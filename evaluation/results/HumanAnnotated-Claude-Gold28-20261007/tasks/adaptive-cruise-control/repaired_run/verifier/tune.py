"""Grid-search PID gains for speed and distance loops; write tuning_results.yaml.

This script is used offline to produce tuning_results.yaml. simulation.py never
imports from here; it just loads the resulting yaml file.
"""

import copy
import itertools
import pandas as pd
import yaml

from acc_system import AdaptiveCruiseControl


def simulate(config, sensor_df):
    dt = config['simulation']['dt']
    max_a = config['vehicle']['max_acceleration']
    min_a = config['vehicle']['max_deceleration']
    acc = AdaptiveCruiseControl(config)

    ego_speed = 0.0
    sim_distance = None
    prev_lead = False
    rows = []
    for _, r in sensor_df.iterrows():
        lead_speed = None if pd.isna(r['lead_speed']) else float(r['lead_speed'])
        sensor_d = None if pd.isna(r['distance']) else float(r['distance'])

        lead_present = lead_speed is not None
        if lead_present and not prev_lead:
            sim_distance = sensor_d
        elif not lead_present:
            sim_distance = None
        prev_lead = lead_present

        a, mode, derr = acc.compute(ego_speed, lead_speed, sim_distance, dt)
        a = max(min_a, min(max_a, a))

        rows.append((r['time'], ego_speed, a, mode, derr, sim_distance, lead_speed))

        ego_speed = max(0.0, ego_speed + a * dt)
        if sim_distance is not None and lead_speed is not None:
            sim_distance = max(0.0, sim_distance + (lead_speed - ego_speed) * dt)
    return rows


def rise_time(times, values, target):
    t10 = t90 = None
    for t, v in zip(times, values):
        if t10 is None and v >= 0.1 * target:
            t10 = t
        if t90 is None and v >= 0.9 * target:
            t90 = t
            return t90 - t10
    return None


def overshoot_pct(values, target):
    m = max(values)
    return 0.0 if m <= target else (m - target) / target * 100.0


def eval_speed(rows):
    """Evaluate cruise segments (mode == 'cruise') for speed metrics."""
    cruise = [r for r in rows if r[3] == 'cruise' and r[0] <= 30.0]
    times = [r[0] for r in cruise]
    speeds = [r[1] for r in cruise]
    target = 30.0
    rt = rise_time(times, speeds, target)
    ov = overshoot_pct(speeds, target)
    # steady state over final 5s of initial cruise segment (25-30s)
    final = [s for t, s in zip(times, speeds) if 25.0 <= t <= 30.0]
    sse = abs(target - sum(final) / len(final)) if final else float('inf')
    return rt, ov, sse


def eval_distance(rows):
    """Distance SSE during a steady-reference window (t in [40,70]s).

    The lead vehicle holds ~25 m/s with low variance (std<1) over t=35-72s;
    we measure mean absolute distance error there, which matches the
    'mean absolute error in each steady segment' guidance for a changing
    reference. min_d is reported across the entire follow interval.
    """
    follow = [r for r in rows if r[3] in ('follow', 'emergency') and r[4] is not None]
    if not follow:
        return float('inf'), float('inf')
    steady = [r for r in follow if 40.0 <= r[0] <= 70.0]
    errs = [abs(r[4]) for r in steady]
    sse = sum(errs) / len(errs) if errs else float('inf')
    min_d = min(r[5] for r in rows if r[5] is not None)
    return sse, min_d


def main():
    with open('vehicle_params.yaml', 'r') as f:
        base = yaml.safe_load(f)
    sensor_df = pd.read_csv('sensor_data.csv')

    # --- Speed PID tuning (gains must satisfy kp in (0,10), ki/kd in [0,5)) ---
    print("=== Speed PID tuning ===")
    speed_candidates = []
    for kp, ki, kd in itertools.product(
        [0.3, 0.5, 0.8, 1.0, 1.5, 2.0],
        [0.0, 0.05, 0.1, 0.2, 0.5],
        [0.0, 0.05, 0.1],
    ):
        cfg = copy.deepcopy(base)
        cfg['pid_speed'] = {'kp': kp, 'ki': ki, 'kd': kd}
        cfg['pid_distance'] = {'kp': 0.3, 'ki': 0.02, 'kd': 1.5}
        rows = simulate(cfg, sensor_df)
        rt, ov, sse = eval_speed(rows)
        ok = rt is not None and rt < 10.0 and ov < 5.0 and sse < 0.5
        speed_candidates.append((ok, rt or 999, ov, sse, kp, ki, kd))

    speed_candidates.sort(key=lambda x: (not x[0], x[1], x[2], x[3]))
    best = speed_candidates[0]
    print(f"Best speed: kp={best[4]} ki={best[5]} kd={best[6]} | "
          f"rise={best[1]:.2f}s overshoot={best[2]:.2f}% sse={best[3]:.3f}")
    best_speed = {'kp': best[4], 'ki': best[5], 'kd': best[6]}

    # --- Distance PID tuning ---
    print("=== Distance PID tuning ===")
    dist_candidates = []
    for kp, ki, kd in itertools.product(
        [0.3, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0],
        [0.0, 0.01, 0.05, 0.1, 0.2],
        [1.0, 2.0, 3.0, 4.0, 4.5],
    ):
        cfg = copy.deepcopy(base)
        cfg['pid_speed'] = best_speed
        cfg['pid_distance'] = {'kp': kp, 'ki': ki, 'kd': kd}
        rows = simulate(cfg, sensor_df)
        sse, min_d = eval_distance(rows)
        ok = sse < 2.0 and min_d > 5.0
        dist_candidates.append((ok, sse, -min_d, kp, ki, kd, min_d))

    dist_candidates.sort(key=lambda x: (not x[0], x[1], x[2]))
    print("Top 8 distance candidates:")
    for c in dist_candidates[:8]:
        print(f"  ok={c[0]} kp={c[3]} ki={c[4]} kd={c[5]} sse={c[1]:.3f} min_d={c[6]:.2f}")
    best_d = dist_candidates[0]
    print(f"Best distance: kp={best_d[3]} ki={best_d[4]} kd={best_d[5]} | "
          f"sse={best_d[1]:.3f} min_d={best_d[6]:.2f}")
    best_dist = {'kp': best_d[3], 'ki': best_d[4], 'kd': best_d[5]}

    out = {'pid_speed': best_speed, 'pid_distance': best_dist}
    with open('tuning_results.yaml', 'w') as f:
        yaml.dump(out, f, default_flow_style=False, sort_keys=False)
    print("Wrote tuning_results.yaml")


if __name__ == '__main__':
    main()
