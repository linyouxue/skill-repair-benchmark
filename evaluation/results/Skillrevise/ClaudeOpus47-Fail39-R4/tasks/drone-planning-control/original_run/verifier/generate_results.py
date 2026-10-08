import json
import os
from glob import glob

import numpy as np

from params import load_params
from flight_plan_parser import parse_flight_plan
from trajectory_planner import trajectory_planner
from simulate import simulate_trajectory
from stepinfo_3d import stepinfo_3d
from plot_quadrotor import plot_quadrotor


def _accel_limits_ok(params: dict, planned: np.ndarray) -> bool:
    acc = planned[12:15, :]
    ax, ay, az = acc[0, :], acc[1, :], acc[2, :]
    horiz = np.sqrt(ax**2 + ay**2)

    if np.any(az > float(params['accel_limit_up']) + 1e-9):
        return False
    if np.any(az < -float(params['accel_limit_down']) - 1e-9):
        return False
    if np.any(horiz > float(params['accel_limit_horiz']) + 1e-9):
        return False
    return True


def _score_run(planned: np.ndarray, actual: np.ndarray, metrics: dict) -> float:
    pos_err = np.linalg.norm((actual[0:3, :] - planned[0:3, :]).T, axis=1)
    max_err = float(np.max(pos_err))

    score = max_err
    score += 0.2 * float(metrics['SteadyStateError'])
    score += 0.01 * float(metrics['Overshoot_pct'])
    score += 0.001 * float(metrics['SettlingTime'])

    if max_err > 0.05:
        score += 1000.0 * (max_err - 0.05)
    if metrics['SteadyStateError'] >= 0.05:
        score += 1000.0 * (metrics['SteadyStateError'] - 0.05)
    if metrics['Overshoot_pct'] >= 5.0:
        score += 1000.0 * (metrics['Overshoot_pct'] - 5.0)

    return score


def tune_and_run_for_command(params_base: dict, command_text: str):
    waypoints, waypoint_times, modes = parse_flight_plan(command_text)
    time_final = float(waypoint_times[-1])
    sr = float(params_base['sample_rate'])
    max_iter = int(np.ceil(time_final * sr)) + 1

    planned = trajectory_planner(waypoints, max_iter, waypoint_times, sr, modes)
    if not _accel_limits_ok(params_base, planned):
        raise RuntimeError('Planned trajectory violates acceleration limits')

    candidates = []

    kp_pos_base = np.array([4.0, 4.0, 8.0])
    kd_pos_base = np.array([3.0, 3.0, 5.0])
    ki_pos_base = np.array([0.0, 0.0, 0.5])

    kp_att_base = np.array([220.0, 220.0, 120.0])
    kd_att_base = np.array([35.0, 35.0, 20.0])
    ki_att_base = np.array([0.0, 0.0, 0.0])

    for s_pos in [0.7, 1.0, 1.3]:
        for s_att in [0.7, 1.0, 1.3]:
            candidates.append(
                {
                    'kp_pos': (kp_pos_base * s_pos).tolist(),
                    'ki_pos': (ki_pos_base * s_pos).tolist(),
                    'kd_pos': (kd_pos_base * s_pos).tolist(),
                    'kp_att': (kp_att_base * s_att).tolist(),
                    'ki_att': (ki_att_base * s_att).tolist(),
                    'kd_att': (kd_att_base * s_att).tolist(),
                }
            )

    best = None
    best_score = float('inf')
    best_actual = None
    best_metrics = None

    t = np.arange(max_iter, dtype=float) / sr
    pos_target = waypoints[0:3, -1]

    for cand in candidates:
        params = dict(params_base)
        params.update(cand)
        actual = simulate_trajectory(params, planned)
        metrics = stepinfo_3d(actual[0:3, :], pos_target, t, settling_threshold=0.02)
        metrics = {'mode': modes[0], **metrics}
        score = _score_run(planned, actual, metrics)
        if score < best_score:
            best_score = score
            best = cand
            best_actual = actual
            best_metrics = metrics

    return planned, best_actual, best_metrics, best


def main():
    params = load_params('/root/system_params.yaml')

    cmd_files = sorted(glob('/root/commands/*.txt'))
    os.makedirs('/root/results', exist_ok=True)

    for path in cmd_files:
        label = os.path.splitext(os.path.basename(path))[0]
        out_dir = f'/root/results/{label}'
        os.makedirs(out_dir, exist_ok=True)

        with open(path, 'r') as f:
            cmd_text = f.read()

        planned, actual, metrics, tuning = tune_and_run_for_command(params, cmd_text)

        np.save(os.path.join(out_dir, 'planned_trajectory.npy'), planned)
        np.save(os.path.join(out_dir, 'actual_trajectory.npy'), actual)

        with open(os.path.join(out_dir, 'metrics_3d.json'), 'w') as f:
            json.dump(metrics, f, indent=2)

        with open(os.path.join(out_dir, 'tuning_results.json'), 'w') as f:
            json.dump(tuning, f, indent=2)

        plot_quadrotor(
            actual,
            planned,
            np.arange(planned.shape[1]) / float(params['sample_rate']),
            save_dir=os.path.join(out_dir, 'plots'),
        )


if __name__ == '__main__':
    main()
