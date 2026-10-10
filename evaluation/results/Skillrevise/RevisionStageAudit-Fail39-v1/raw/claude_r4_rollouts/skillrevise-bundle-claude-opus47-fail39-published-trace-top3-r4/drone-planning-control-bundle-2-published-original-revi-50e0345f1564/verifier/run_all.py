"""Top-level orchestrator: parse each command, plan, simulate, verify, write artifacts."""

import json
import os
import sys
import numpy as np
import yaml

from flight_plan_parser import parse_flight_plan
from trajectory_planner import plan_trajectory, check_acceleration_limits
from simulator import simulate
from metrics import stepinfo_3d
from plot_results import plot_results


ROOT = '/root'
COMMANDS_DIR = os.path.join(ROOT, 'commands')
RESULTS_DIR = os.path.join(ROOT, 'results')
PARAMS_PATH = os.path.join(ROOT, 'system_params.yaml')


# Reasonable baseline gains that work across modes
DEFAULT_GAINS = {
    'kp_pos': [6.0, 6.0, 10.0],
    'ki_pos': [0.5, 0.5, 1.5],
    'kd_pos': [4.5, 4.5, 6.0],
    'kp_att': [180.0, 180.0, 60.0],
    'ki_att': [0.0, 0.0, 0.0],
    'kd_att': [25.0, 25.0, 15.0],
}


def _gains_for_mode(mode):
    g = {k: list(v) for k, v in DEFAULT_GAINS.items()}
    if mode == 'fly':
        # Fast horizontal response: higher position + attitude bandwidth
        g['kp_pos'] = [14.0, 14.0, 10.0]
        g['kd_pos'] = [7.0, 7.0, 6.0]
        g['ki_pos'] = [1.0, 1.0, 1.5]
        g['kp_att'] = [320.0, 320.0, 60.0]
        g['kd_att'] = [34.0, 34.0, 15.0]
    return g


def _run_one(cmd_path):
    name = os.path.splitext(os.path.basename(cmd_path))[0]
    with open(cmd_path) as f:
        text = f.read()

    with open(PARAMS_PATH) as f:
        params = yaml.safe_load(f)

    waypoints, waypoint_times, modes = parse_flight_plan(text)
    assert len(modes) == 1, f'expected single-segment command, got {modes}'
    mode = modes[0]

    planned, time_vec = plan_trajectory(waypoints, waypoint_times, modes, params['sample_rate'])

    ok, mu, md, mh = check_acceleration_limits(planned, params)
    assert ok, f'[{name}] planned acceleration exceeds limits: up={mu}, down={md}, horiz={mh}'

    gains = _gains_for_mode(mode)

    initial_pos = waypoints[0:3, 0].copy()
    actual = simulate(planned, time_vec, params, gains, initial_pos)

    # Metrics on 3D distance to final target
    pos_target = waypoints[0:3, -1]
    metrics = stepinfo_3d(actual[0:3, :], pos_target, time_vec, settling_threshold=0.02)
    metrics_out = {'mode': mode, **metrics}

    # Verification
    pos_err = np.linalg.norm(actual[0:3, :] - planned[0:3, :], axis=0)
    max_pos_err = float(pos_err.max())
    sse = metrics['SteadyStateError']
    overshoot = metrics['Overshoot_pct']

    pass_track = max_pos_err < 0.05
    pass_sse = sse < 0.05
    pass_over = overshoot < 5.0
    verdict = pass_track and pass_sse and pass_over

    out_dir = os.path.join(RESULTS_DIR, name)
    os.makedirs(out_dir, exist_ok=True)

    np.save(os.path.join(out_dir, 'planned_trajectory.npy'), planned)
    np.save(os.path.join(out_dir, 'actual_trajectory.npy'), actual)

    with open(os.path.join(out_dir, 'metrics_3d.json'), 'w') as f:
        json.dump(metrics_out, f, indent=2)

    with open(os.path.join(out_dir, 'tuning_results.json'), 'w') as f:
        json.dump(gains, f, indent=2)

    plot_results(actual, planned, time_vec, os.path.join(out_dir, 'plots'), PARAMS_PATH)

    # Reload-and-assert verification anchor
    _p = np.load(os.path.join(out_dir, 'planned_trajectory.npy'))
    _a = np.load(os.path.join(out_dir, 'actual_trajectory.npy'))
    assert _p.shape == (15, time_vec.size), f'planned shape {_p.shape}'
    assert _a.shape == (15, time_vec.size), f'actual shape {_a.shape}'
    with open(os.path.join(out_dir, 'metrics_3d.json')) as f:
        _m = json.load(f)
    assert set(_m) >= {'mode', 'RiseTime', 'SettlingTime', 'Overshoot_pct', 'SteadyStateError'}
    with open(os.path.join(out_dir, 'tuning_results.json')) as f:
        _g = json.load(f)
    assert set(_g) == {'kp_pos', 'ki_pos', 'kd_pos', 'kp_att', 'ki_att', 'kd_att'}

    status = 'PASS' if verdict else 'FAIL'
    print(f'[{status}] {name} mode={mode:7s} '
          f'max_err={max_pos_err:.4f}m  SSE={sse:.4f}m  OS={overshoot:.2f}%  '
          f'acc_margins up={params["accel_limit_up"]-mu:.2f} '
          f'dn={params["accel_limit_down"]-md:.2f} '
          f'hz={params["accel_limit_horiz"]-mh:.2f}')

    return verdict, max_pos_err, metrics_out


def main(argv):
    if len(argv) > 1:
        files = []
        for a in argv[1:]:
            if os.path.isabs(a) or os.path.exists(a):
                files.append(a)
            else:
                files.append(os.path.join(COMMANDS_DIR, a))
    else:
        files = sorted(os.path.join(COMMANDS_DIR, f) for f in os.listdir(COMMANDS_DIR)
                       if f.endswith('.txt'))

    os.makedirs(RESULTS_DIR, exist_ok=True)
    fails = []
    for f in files:
        try:
            ok, _, _ = _run_one(f)
            if not ok:
                fails.append(os.path.basename(f))
        except Exception as e:
            print(f'[ERROR] {os.path.basename(f)}: {e}')
            fails.append(os.path.basename(f))

    print('---')
    if fails:
        print(f'Failed: {fails}')
        sys.exit(1)
    else:
        print('All commands passed.')


if __name__ == '__main__':
    main(sys.argv)
