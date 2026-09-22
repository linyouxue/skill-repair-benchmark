import argparse
import glob
import json
import os

import numpy as np

from drone_params import load_system_params
from flight_plan_parser import parse_flight_plan
from plot_quadrotor import plot_quadrotor
from simulate import simulate_trajectory
from stepinfo_3d import stepinfo_3d
from trajectory_planner import trajectory_planner
from tuner import tune_pid_for_command


def _ensure_float_list(x):
    return [float(v) for v in x]


def run_one_command(command_path: str, results_root: str, params: dict) -> None:
    label = os.path.splitext(os.path.basename(command_path))[0]
    out_dir = os.path.join(results_root, label)
    os.makedirs(out_dir, exist_ok=True)

    with open(command_path, "r") as f:
        text = f.read().strip()

    waypoints, waypoint_times, modes = parse_flight_plan(text)

    sample_rate = float(params["sample_rate"])
    time_final = float(waypoint_times[-1])
    max_iter = int(time_final * sample_rate) + 1
    max_iter = max(max_iter, 2)

    planned = trajectory_planner(
        waypoints,
        max_iter,
        waypoint_times,
        sample_rate,
        modes,
        params=params,
    )

    np.save(os.path.join(out_dir, "planned_trajectory.npy"), planned)

    best_gains, _ = tune_pid_for_command(planned, params)

    tuning_out = {
        "kp_pos": _ensure_float_list(best_gains["kp_pos"]),
        "ki_pos": _ensure_float_list(best_gains["ki_pos"]),
        "kd_pos": _ensure_float_list(best_gains["kd_pos"]),
        "kp_att": _ensure_float_list(best_gains["kp_att"]),
        "ki_att": _ensure_float_list(best_gains["ki_att"]),
        "kd_att": _ensure_float_list(best_gains["kd_att"]),
    }

    with open(os.path.join(out_dir, "tuning_results.json"), "w") as f:
        json.dump(tuning_out, f, indent=2)

    actual, time_vec, _ = simulate_trajectory(planned, params, best_gains)

    np.save(os.path.join(out_dir, "actual_trajectory.npy"), actual)

    metrics = stepinfo_3d(
        actual[0:3, :],
        planned[0:3, -1],
        time_vec,
        settling_threshold=0.02,
    )

    metrics_out = {
        "mode": str(modes[0]) if modes else "unknown",
        "RiseTime": float(metrics["RiseTime"]),
        "SettlingTime": float(metrics["SettlingTime"]),
        "Overshoot_pct": float(metrics["Overshoot_pct"]),
        "SteadyStateError": float(metrics["SteadyStateError"]),
    }

    with open(os.path.join(out_dir, "metrics_3d.json"), "w") as f:
        json.dump(metrics_out, f, indent=2)

    plot_quadrotor(actual, planned, time_vec, save_dir=os.path.join(out_dir, "plots"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--commands_dir", default="/root/commands")
    ap.add_argument("--results_dir", default="/root/results")
    ap.add_argument("--params", default="/root/system_params.yaml")
    args = ap.parse_args()

    params = load_system_params(args.params)
    os.makedirs(args.results_dir, exist_ok=True)

    cmd_files = sorted(glob.glob(os.path.join(args.commands_dir, "*.txt")))
    for path in cmd_files:
        run_one_command(path, args.results_dir, params)


if __name__ == "__main__":
    main()
