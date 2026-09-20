import os
import json
import glob
import numpy as np
import yaml

from flight_plan_parser import parse_flight_plan
from trajectory_planner import trajectory_planner
from controllers import (
    position_controller, attitude_planner, attitude_controller,
    make_position_integral, make_attitude_integral,
)
from motor_model import motor_model, build_prop_matrix
from dynamics import rk45_step
from stepinfo_3d import stepinfo_3d
from plot_quadrotor import plot_quadrotor


def load_params():
    with open('/root/system_params.yaml') as f:
        p = yaml.safe_load(f)
    p['inertia'] = list(p['inertia'])
    return p


def hover_rpm(params):
    """RPM required for each motor to produce mg/4 thrust."""
    cT = params['thrust_coefficient']
    mass = params['mass']; g = params['gravity']
    return float(np.sqrt(mass * g / (4 * cT)))


def simulate(waypoints, waypoint_times, modes, params, gains):
    """Run the closed-loop simulation and return actual+desired 15-row matrices."""
    params = {**params, **gains}
    sample_rate = params['sample_rate']
    dt = 1.0 / sample_rate
    t_end = float(waypoint_times[-1])
    max_iter = int(round(t_end * sample_rate)) + 1
    time_vec = np.arange(max_iter) * dt

    # Plan the reference trajectory
    desired = trajectory_planner(waypoints, max_iter, waypoint_times, sample_rate, modes)

    # Initial state — start at first waypoint
    state16 = np.zeros(16)
    state16[0:3] = waypoints[0:3, 0]
    state16[8]   = waypoints[3, 0]   # yaw
    state16[12:16] = hover_rpm(params)

    actual = np.zeros((15, max_iter))
    pos_int = make_position_integral()
    att_int = make_attitude_integral()

    P = build_prop_matrix(params)  # not strictly needed here

    prev_vel = state16[3:6].copy()
    for k in range(max_iter):
        # log actual state
        actual[0:3, k]  = state16[0:3]
        actual[3:6, k]  = state16[3:6]
        actual[6:9, k]  = state16[6:9]
        actual[9:12, k] = state16[9:12]
        # actual accel — from finite difference of velocity
        if k > 0:
            actual[12:15, k] = (state16[3:6] - prev_vel) / dt
        prev_vel = state16[3:6].copy()

        if k == max_iter - 1:
            break

        des_pos = desired[0:3, k]
        des_vel = desired[3:6, k]
        des_acc = desired[12:15, k]
        des_yaw = desired[8, k]
        des_yaw_rate = desired[11, k]

        F, acc_cmd = position_controller(
            state16[0:3], state16[3:6],
            des_pos, des_vel, des_acc,
            params, pos_int)

        rot_des, omega_des = attitude_planner(acc_cmd, des_yaw, des_yaw_rate, params)
        M = attitude_controller(state16[6:9], state16[9:12],
                                rot_des, omega_des, params, att_int)

        F_actual, M_actual, rpm_dot = motor_model(F, M, state16[12:16], params)
        state16 = rk45_step(params, state16, F_actual, M_actual, rpm_dot, dt)

    return desired, actual, time_vec


def check_traj_limits(desired, params):
    az = desired[14]
    axy = np.hypot(desired[12], desired[13])
    ok_up   = np.all(az <=  params['accel_limit_up']   + 1e-6)
    ok_down = np.all(az >= -params['accel_limit_down'] - 1e-6)
    ok_hor  = np.all(axy <= params['accel_limit_horiz'] + 1e-6)
    return ok_up and ok_down and ok_hor


def eval_run(desired, actual, waypoints, time_vec):
    target = waypoints[0:3, -1]
    m = stepinfo_3d(actual[0:3], target, time_vec, settling_threshold=0.02)
    # per-step position error
    err = np.linalg.norm(actual[0:3] - desired[0:3], axis=0)
    m['MaxPosErr'] = float(np.max(err))
    return m


def score(metrics, ok_limits):
    """Lower is better. Heavy penalty if limits violated."""
    penalty = 0.0
    if not ok_limits:
        penalty += 1e6
    if metrics['SteadyStateError'] > 0.05:
        penalty += (metrics['SteadyStateError'] - 0.05) * 100
    if metrics['Overshoot_pct'] > 5.0:
        penalty += (metrics['Overshoot_pct'] - 5.0) * 10
    if metrics['MaxPosErr'] > 0.05:
        penalty += (metrics['MaxPosErr'] - 0.05) * 100
    # tie-breaker: minimise max position error
    return penalty + metrics['MaxPosErr']


def tune(waypoints, waypoint_times, modes, params, candidate_gains):
    best = None
    best_score = np.inf
    best_run = None
    for gains in candidate_gains:
        desired, actual, tvec = simulate(waypoints, waypoint_times, modes, params, gains)
        ok_lim = check_traj_limits(desired, params)
        m = eval_run(desired, actual, waypoints, tvec)
        s = score(m, ok_lim)
        if s < best_score:
            best_score = s
            best = gains
            best_run = (desired, actual, tvec, m, ok_lim)
    return best, best_run, best_score


def default_candidates():
    """A modest sweep — start from a good baseline and vary key gains."""
    baselines = [
        dict(
            kp_pos=[6.0, 6.0, 12.0],
            ki_pos=[0.5, 0.5, 3.0],
            kd_pos=[4.0, 4.0, 6.0],
            kp_att=[180.0, 180.0, 80.0],
            ki_att=[0.0, 0.0, 0.0],
            kd_att=[25.0, 25.0, 20.0],
        ),
        dict(
            kp_pos=[8.0, 8.0, 15.0],
            ki_pos=[1.0, 1.0, 4.0],
            kd_pos=[5.0, 5.0, 7.0],
            kp_att=[220.0, 220.0, 100.0],
            ki_att=[0.0, 0.0, 0.0],
            kd_att=[30.0, 30.0, 25.0],
        ),
        dict(
            kp_pos=[4.0, 4.0, 10.0],
            ki_pos=[0.2, 0.2, 2.0],
            kd_pos=[3.5, 3.5, 5.5],
            kp_att=[150.0, 150.0, 60.0],
            ki_att=[0.0, 0.0, 0.0],
            kd_att=[22.0, 22.0, 18.0],
        ),
        dict(
            kp_pos=[10.0, 10.0, 20.0],
            ki_pos=[1.5, 1.5, 5.0],
            kd_pos=[6.0, 6.0, 9.0],
            kp_att=[260.0, 260.0, 120.0],
            ki_att=[0.0, 0.0, 0.0],
            kd_att=[35.0, 35.0, 30.0],
        ),
    ]
    return baselines


def process_command(cmd_path, params, results_root='/root/results'):
    label = os.path.splitext(os.path.basename(cmd_path))[0]
    out_dir = os.path.join(results_root, label)
    os.makedirs(out_dir, exist_ok=True)

    with open(cmd_path) as f:
        text = f.read().strip()

    waypoints, waypoint_times, modes = parse_flight_plan(text)

    best_gains, best_run, best_score = tune(
        waypoints, waypoint_times, modes, params, default_candidates())
    desired, actual, tvec, metrics, ok_lim = best_run

    # write outputs
    np.save(os.path.join(out_dir, 'planned_trajectory.npy'), desired)
    np.save(os.path.join(out_dir, 'actual_trajectory.npy'),  actual)

    with open(os.path.join(out_dir, 'metrics_3d.json'), 'w') as f:
        json.dump({
            'mode': modes[-1],
            'RiseTime': metrics['RiseTime'],
            'SettlingTime': metrics['SettlingTime'],
            'Overshoot_pct': metrics['Overshoot_pct'],
            'SteadyStateError': metrics['SteadyStateError'],
        }, f, indent=2)

    with open(os.path.join(out_dir, 'tuning_results.json'), 'w') as f:
        json.dump(best_gains, f, indent=2)

    plot_quadrotor(actual, desired, tvec, save_dir=os.path.join(out_dir, 'plots'))

    return {
        'label': label,
        'mode': modes[-1],
        'MaxPosErr': metrics['MaxPosErr'],
        'metrics': metrics,
        'limits_ok': ok_lim,
        'score': best_score,
    }


def main():
    params = load_params()
    cmd_files = sorted(glob.glob('/root/commands/*.txt'))
    summary = []
    for cf in cmd_files:
        info = process_command(cf, params)
        summary.append(info)
        m = info['metrics']
        print(f"{info['label']} {info['mode']:8s}  "
              f"SSE={m['SteadyStateError']:.4f}  OS={m['Overshoot_pct']:.2f}%  "
              f"MaxErr={m['MaxPosErr']:.4f}  lim_ok={info['limits_ok']}")
    return summary


if __name__ == '__main__':
    main()
