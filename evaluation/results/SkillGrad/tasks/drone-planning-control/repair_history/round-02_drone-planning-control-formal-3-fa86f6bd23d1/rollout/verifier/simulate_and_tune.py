from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from controllers import attitude_controller, attitude_planner, position_controller
from flight_plan_parser import parse_flight_plan
from motor_dynamics import accel_from_thrust, motor_model, step_dynamics_rk45
from plot_quadrotor import plot_trajectories
from stepinfo_3d import stepinfo_3d
from trajectory_planner import trajectory_planner
from utils import CurrentState, DesiredState, load_params, make_attitude_integral, make_position_integral


@dataclass
class SimResult:
    planned: np.ndarray
    actual: np.ndarray
    time: np.ndarray
    metrics: dict
    max_pos_err: float


def simulate_once(command_text: str, gains: dict) -> SimResult:
    params = load_params()
    params.update(gains)

    waypoints, waypoint_times, modes = parse_flight_plan(command_text)
    sample_rate = float(params['sample_rate'])

    planned = trajectory_planner(waypoints, waypoint_times, sample_rate, modes, params)

    max_iter = planned.shape[1]
    dt = 1.0 / sample_rate
    time = np.arange(max_iter, dtype=float) * dt

    s = np.zeros(16, dtype=float)
    s[0:3] = planned[0:3, 0]
    s[3:6] = planned[3:6, 0]
    s[6:9] = planned[6:9, 0]
    s[9:12] = planned[9:12, 0]

    cT = float(params['thrust_coefficient'])
    m = float(params['mass'])
    g = float(params['gravity'])
    rpm_hover = np.sqrt((m * g) / (4.0 * cT))
    rpm_hover = float(np.clip(rpm_hover, float(params['rpm_min']), float(params['rpm_max'])))
    s[12:16] = rpm_hover

    actual = np.zeros((15, max_iter), dtype=float)

    pos_int = make_position_integral()
    att_int = make_attitude_integral()

    for k in range(max_iter):
        pos = s[0:3].copy()
        vel = s[3:6].copy()
        rot = s[6:9].copy()
        omega = s[9:12].copy()
        rpm = s[12:16].copy()

        cur = CurrentState(pos=pos, vel=vel, rot=rot, omega=omega, rpm=rpm)
        des = DesiredState(
            pos=planned[0:3, k].copy(),
            vel=planned[3:6, k].copy(),
            rot=planned[6:9, k].copy(),
            omega=planned[9:12, k].copy(),
            acc=planned[12:15, k].copy(),
        )

        F_des, acc_cmd = position_controller(cur, des, params, pos_int)
        des.acc = acc_cmd
        des.rot, des.omega = attitude_planner(des, params)
        M_des = attitude_controller(cur, des, params, att_int)

        F_act, M_act, rpm_dot = motor_model(params, rpm, F_des, M_des)

        actual[0:3, k] = pos
        actual[3:6, k] = vel
        actual[6:9, k] = rot
        actual[9:12, k] = omega
        actual[12:15, k] = accel_from_thrust(params, rot, F_act)

        if k < max_iter - 1:
            s = step_dynamics_rk45(params, s, F_act, M_act, rpm_dot)

    pos_err = np.linalg.norm(actual[0:3, :] - planned[0:3, :], axis=0)
    max_pos_err = float(np.max(pos_err))

    pos_target = planned[0:3, -1]
    metrics = stepinfo_3d(actual[0:3, :], pos_target, time, settling_threshold=0.02)
    metrics = {'mode': modes[0] if modes else 'unknown', **metrics}

    return SimResult(planned=planned, actual=actual, time=time, metrics=metrics, max_pos_err=max_pos_err)


def is_planned_within_limits(planned: np.ndarray, params: dict) -> bool:
    ax = planned[12, :]
    ay = planned[13, :]
    az = planned[14, :]
    horiz = np.sqrt(ax**2 + ay**2)

    if np.any(horiz > float(params['accel_limit_horiz']) + 1e-9):
        return False
    if np.any(az > float(params['accel_limit_up']) + 1e-9):
        return False
    if np.any(az < -float(params['accel_limit_down']) - 1e-9):
        return False
    return True


def tune_command(command_text: str):
    params = load_params()

    base = {
        'kp_pos': np.array([8.0, 8.0, 10.0]),
        'ki_pos': np.array([0.0, 0.0, 0.0]),
        'kd_pos': np.array([5.0, 5.0, 6.0]),
        'kp_att': np.array([350.0, 350.0, 120.0]),
        'ki_att': np.array([0.0, 0.0, 0.0]),
        'kd_att': np.array([30.0, 30.0, 10.0]),
    }

    scales = [0.5, 0.8, 1.0, 1.2, 1.5]

    best = None
    best_score = float('inf')

    for sp in scales:
        for sa in scales:
            gains = {
                'kp_pos': (base['kp_pos'] * sp).tolist(),
                'ki_pos': base['ki_pos'].tolist(),
                'kd_pos': (base['kd_pos'] * sp).tolist(),
                'kp_att': (base['kp_att'] * sa).tolist(),
                'ki_att': base['ki_att'].tolist(),
                'kd_att': (base['kd_att'] * sa).tolist(),
            }

            res = simulate_once(command_text, gains)

            ok = (
                res.metrics['SteadyStateError'] < 0.05
                and res.metrics['Overshoot_pct'] < 5.0
                and res.max_pos_err < 0.05
            )

            score = (
                1000.0 * res.max_pos_err
                + 10.0 * res.metrics['SteadyStateError']
                + 0.1 * res.metrics['Overshoot_pct']
                + 0.01 * res.metrics['SettlingTime']
            )
            if ok:
                score *= 0.1

            if score < best_score:
                best_score = score
                best = (gains, res)

    assert best is not None

    gains, res = best
    params.update(gains)
    assert is_planned_within_limits(res.planned, params)

    return gains, res


def run_all(commands_dir: str | Path = '/root/commands', results_root: str | Path = '/root/results'):
    commands_dir = Path(commands_dir)
    results_root = Path(results_root)
    results_root.mkdir(parents=True, exist_ok=True)

    for path in sorted(commands_dir.glob('*.txt')):
        cmd_id = path.stem
        text = path.read_text(encoding='utf-8')

        gains, res = tune_command(text)

        out_dir = results_root / cmd_id
        plots_dir = out_dir / 'plots'
        plots_dir.mkdir(parents=True, exist_ok=True)

        np.save(out_dir / 'planned_trajectory.npy', res.planned)
        np.save(out_dir / 'actual_trajectory.npy', res.actual)

        with open(out_dir / 'metrics_3d.json', 'w', encoding='utf-8') as f:
            json.dump(res.metrics, f, indent=2)

        with open(out_dir / 'tuning_results.json', 'w', encoding='utf-8') as f:
            json.dump(gains, f, indent=2)

        plot_trajectories(res.actual, res.planned, res.time, plots_dir)


if __name__ == '__main__':
    run_all()
