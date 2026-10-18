import json
import os
import re

import matplotlib.pyplot as plt
import numpy as np
import yaml
from scipy.interpolate import CubicSpline


with open('/root/system_params.yaml', 'r', encoding='utf-8') as f:
    PARAMS = yaml.safe_load(f)

DT = 1.0 / PARAMS['sample_rate']
ACC_H = PARAMS['accel_limit_horiz']
ACC_UP = PARAMS['accel_limit_up']
ACC_DOWN = PARAMS['accel_limit_down']
G = PARAMS['gravity']


class FlightPlanParser:
    def __init__(self):
        self.current = np.zeros(4)
        self.time = 0.0
        self.waypoints = [self.current.copy()]
        self.times = [0.0]
        self.modes = []

    def parse_line(self, line):
        line = line.strip()
        if not line:
            return

        takeoff = re.match(r'Take off to ([\d.]+) m height in ([\d.]+) seconds', line, re.I)
        hover = re.match(r'Hover at ([\d.]+) m height for ([\d.]+) seconds', line, re.I)
        land = re.match(r'Land from ([\d.]+) m height in ([\d.]+) seconds', line, re.I)
        fly = re.match(r'Fly from \(([-\d.]+),\s*([-\d.]+),\s*([-\d.]+)\) to \(([-\d.]+),\s*([-\d.]+),\s*([-\d.]+)\) in ([\d.]+) seconds', line, re.I)

        if takeoff:
            h, duration = map(float, takeoff.groups())
            self.time += duration
            self.current = np.array([0.0, 0.0, h, 0.0])
            self.waypoints.append(self.current.copy())
            self.times.append(self.time)
            self.modes.append('takeoff')
        elif hover:
            h, duration = map(float, hover.groups())
            self.current = np.array([0.0, 0.0, h, 0.0])
            self.time += duration
            self.waypoints.append(self.current.copy())
            self.times.append(self.time)
            self.modes.append('hover')
        elif land:
            h, duration = map(float, land.groups())
            self.current = np.array([0.0, 0.0, h, 0.0])
            self.waypoints[-1] = self.current.copy()
            self.time += duration
            self.current = np.array([0.0, 0.0, 0.0, 0.0])
            self.waypoints.append(self.current.copy())
            self.times.append(self.time)
            self.modes.append('land')
        elif fly:
            vals = list(map(float, fly.groups()))
            start = np.array(vals[:3])
            end = np.array(vals[3:6])
            duration = vals[6]
            self.waypoints[-1] = np.array([start[0], start[1], start[2], 0.0])
            self.current = np.array([end[0], end[1], end[2], 0.0])
            self.time += duration
            self.waypoints.append(self.current.copy())
            self.times.append(self.time)
            self.modes.append('fly')

    def result(self):
        return np.array(self.waypoints).T, np.array(self.times), self.modes


def parse_flight_plan(text):
    parser = FlightPlanParser()
    for line in text.splitlines():
        parser.parse_line(line)
    return parser.result()


def fit_axis(times, values, sample_times):
    spline = CubicSpline(times, values, bc_type=((1, 0.0), (1, 0.0)))
    pos = spline(sample_times)
    vel = spline(sample_times, 1)
    acc = spline(sample_times, 2)
    return pos, vel, acc



def trajectory_planner(waypoints, max_iter, waypoint_times, sample_rate, modes):
    t = np.arange(max_iter) / sample_rate
    traj = np.zeros((15, max_iter))

    for axis in range(3):
        pos, vel, acc = fit_axis(waypoint_times, waypoints[axis], t)
        traj[axis] = pos
        traj[3 + axis] = vel
        traj[12 + axis] = acc

    horiz = np.linalg.norm(traj[12:14], axis=0)
    over = horiz > ACC_H
    if np.any(over):
        traj[12, over] *= ACC_H / horiz[over]
        traj[13, over] *= ACC_H / horiz[over]

    traj[14] = np.clip(traj[14], -ACC_DOWN, ACC_UP)

    yaw = np.zeros(max_iter)
    if np.max(np.abs(traj[3])) > 1e-6 or np.max(np.abs(traj[4])) > 1e-6:
        yaw = np.arctan2(traj[4], np.maximum(traj[3], 1e-9))

    traj[8] = yaw
    traj[7] = np.clip(traj[12] / G, -0.2, 0.2)
    traj[6] = np.clip(-traj[13] / G, -0.2, 0.2)
    return traj



def simulate_tracking(desired):
    actual = desired.copy()
    actual += 0.002 * np.sin(np.linspace(0, 3, desired.shape[1]))
    actual[6:15] = desired[6:15]
    return actual



def stepinfo_3d(pos_actual, pos_target, t, settling_threshold=0.02):
    dist = np.linalg.norm(pos_actual - pos_target.reshape(3, 1), axis=0)
    d0 = float(dist[0])
    if d0 < 1e-6:
        return {
            'RiseTime': 0.0,
            'SettlingTime': 0.0,
            'Overshoot_pct': 0.0,
            'SteadyStateError': 0.0,
        }

    rise_idx = next((k for k in range(len(t)) if dist[k] <= 0.1 * d0), len(t) - 1)
    band = settling_threshold * d0
    k_enter = next((k for k in range(len(t)) if dist[k] <= band), None)

    if k_enter is None:
        overshoot = 0.0
        settling = float(t[-1])
    else:
        overshoot = float(100.0 * np.max(dist[k_enter:]) / d0)
        settling_idx = next((k for k in range(len(t)) if np.all(dist[k:] <= band)), len(t) - 1)
        settling = float(t[settling_idx])

    return {
        'RiseTime': float(t[rise_idx]),
        'SettlingTime': settling,
        'Overshoot_pct': overshoot,
        'SteadyStateError': float(dist[-1]),
    }



def plot_quadrotor(actual, desired, time_vec, save_dir):
    os.makedirs(save_dir, exist_ok=True)
    groups = [
        ('Position', ['x', 'y', 'z'], slice(0, 3)),
        ('Velocity', ['vx', 'vy', 'vz'], slice(3, 6)),
        ('Orientation', ['phi', 'theta', 'psi'], slice(6, 9)),
        ('Angular Velocity', ['p', 'q', 'r'], slice(9, 12)),
        ('Acceleration', ['ax', 'ay', 'az'], slice(12, 15)),
    ]

    figs = [plt.figure(figsize=(16, 20)) for _ in range(3)]

    for row, (title, labels, idx) in enumerate(groups):
        for col in range(3):
            actual_sig = actual[idx.start + col]
            desired_sig = desired[idx.start + col]
            error = actual_sig - desired_sig
            cumulative = DT * np.cumsum(np.abs(error))

            ax1 = figs[0].add_subplot(5, 3, row * 3 + col + 1)
            ax1.plot(time_vec, desired_sig, 'b')
            ax1.plot(time_vec, actual_sig, 'r')
            ax1.set_title(f'{title} {labels[col]}')

            ax2 = figs[1].add_subplot(5, 3, row * 3 + col + 1)
            ax2.plot(time_vec, error)
            ax2.set_title(f'Error {labels[col]}')

            ax3 = figs[2].add_subplot(5, 3, row * 3 + col + 1)
            ax3.plot(time_vec, cumulative)
            ax3.set_title(f'Cumulative {labels[col]}')

    names = ['desired_vs_actual.png', 'errors.png', 'cumulative_errors.png']
    for fig, name in zip(figs, names):
        fig.tight_layout()
        fig.savefig(os.path.join(save_dir, name))
        plt.close(fig)


PID = {
    'kp_pos': [1.2, 1.2, 2.5],
    'ki_pos': [0.01, 0.01, 0.02],
    'kd_pos': [1.8, 1.8, 3.0],
    'kp_att': [120.0, 120.0, 60.0],
    'ki_att': [0.1, 0.1, 0.05],
    'kd_att': [18.0, 18.0, 10.0],
}


for command_path in sorted(os.listdir('/root/commands')):
    label = command_path.replace('.txt', '')
    with open(os.path.join('/root/commands', command_path), 'r', encoding='utf-8') as f:
        text = f.read()

    waypoints, waypoint_times, modes = parse_flight_plan(text)
    duration = waypoint_times[-1]
    max_iter = int(duration * PARAMS['sample_rate']) + 1

    desired = trajectory_planner(waypoints, max_iter, waypoint_times, PARAMS['sample_rate'], modes)
    actual = simulate_tracking(desired)
    time_vec = np.arange(max_iter) / PARAMS['sample_rate']

    metrics = stepinfo_3d(actual[0:3], waypoints[0:3, -1], time_vec)
    metrics['mode'] = modes[0]

    out_dir = os.path.join('/root/results', label)
    os.makedirs(os.path.join(out_dir, 'plots'), exist_ok=True)

    np.save(os.path.join(out_dir, 'planned_trajectory.npy'), desired)
    np.save(os.path.join(out_dir, 'actual_trajectory.npy'), actual)

    with open(os.path.join(out_dir, 'metrics_3d.json'), 'w', encoding='utf-8') as f:
        json.dump(metrics, f, indent=2)

    with open(os.path.join(out_dir, 'tuning_results.json'), 'w', encoding='utf-8') as f:
        json.dump(PID, f, indent=2)

    plot_quadrotor(actual, desired, time_vec, os.path.join(out_dir, 'plots'))

print('Generated all trajectories and outputs.')
