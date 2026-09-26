from __future__ import annotations

import json
import os
from dataclasses import asdict
from glob import glob
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

from controllers import Gains
from flight_plan_parser import parse_flight_plan
from plot_quadrotor import plot_results
from simulator import simulate_closed_loop
from stepinfo_3d import stepinfo_3d
from system_params import load_params
from trajectory_planner import trajectory_planner


def _gains_to_jsonable(g: Gains) -> dict:
    return {
        "kp_pos": [float(x) for x in g.kp_pos],
        "ki_pos": [float(x) for x in g.ki_pos],
        "kd_pos": [float(x) for x in g.kd_pos],
        "kp_att": [float(x) for x in g.kp_att],
        "ki_att": [float(x) for x in g.ki_att],
        "kd_att": [float(x) for x in g.kd_att],
    }


def _evaluate(traj: np.ndarray, actual: np.ndarray, mode: str, time_vec: np.ndarray) -> Tuple[dict, float, float]:
    pos_err = np.linalg.norm(actual[0:3, :] - traj[0:3, :], axis=0)
    max_pos_err = float(np.max(pos_err))

    target = traj[0:3, -1]
    metrics = stepinfo_3d(actual[0:3, :], target, time_vec, settling_threshold=0.02)
    metrics_out = {"mode": mode, **metrics}

    sse = float(metrics_out["SteadyStateError"])
    ov = float(metrics_out["Overshoot_pct"])

    # Objective: prioritize passing constraints; otherwise minimize max error.
    obj = 1000.0 * max_pos_err + 50.0 * sse + 1.0 * float(metrics_out["SettlingTime"]) + 0.2 * float(metrics_out["RiseTime"]) + 5.0 * ov
    return metrics_out, obj, max_pos_err


def tune_for_command(traj_state: np.ndarray, time_vec: np.ndarray, mode: str, params: dict) -> Tuple[Gains, np.ndarray, dict]:
    base = Gains(
        kp_pos=np.array([4.5, 4.5, 10.0], dtype=float),
        ki_pos=np.array([0.0, 0.0, 0.0], dtype=float),
        kd_pos=np.array([3.5, 3.5, 7.0], dtype=float),
        kp_att=np.array([220.0, 220.0, 80.0], dtype=float),
        ki_att=np.array([0.0, 0.0, 0.0], dtype=float),
        kd_att=np.array([25.0, 25.0, 10.0], dtype=float),
    )

    pos_scales = [0.7, 1.2, 1.8]
    posd_scales = [0.85, 1.2, 1.4]
    att_scales = [0.7, 1.2, 1.4]
    attd_scales = [0.7, 0.85, 1.2]

    best = None
    best_obj = float("inf")
    best_actual = None
    best_metrics = None

    for sp in pos_scales:
        for sd in posd_scales:
            for sa in att_scales:
                for sad in attd_scales:
                    g = Gains(
                        kp_pos=base.kp_pos * sp,
                        ki_pos=base.ki_pos.copy(),
                        kd_pos=base.kd_pos * sd,
                        kp_att=base.kp_att * sa,
                        ki_att=base.ki_att.copy(),
                        kd_att=base.kd_att * sad,
                    )

                    sim = simulate_closed_loop(traj_state, params, g)
                    metrics_out, obj, max_pos_err = _evaluate(traj_state, sim.actual, mode, time_vec)

                    ok = (
                        metrics_out["SteadyStateError"] < 0.05
                        and metrics_out["Overshoot_pct"] < 5.0
                        and max_pos_err < 0.05
                    )

                    if ok and max_pos_err < 0.02 and metrics_out["SteadyStateError"] < 0.02 and metrics_out["Overshoot_pct"] < 2.5:
                        return g, sim.actual, metrics_out

                    if ok:
                        obj = obj * 0.1

                    if obj < best_obj:
                        best_obj = obj
                        best = g
                        best_actual = sim.actual
                        best_metrics = metrics_out

    assert best is not None and best_actual is not None and best_metrics is not None
    return best, best_actual, best_metrics


def run_all(commands_dir: str = "/root/commands", results_root: str = "/root/results") -> None:
    params = load_params("/root/system_params.yaml")

    os.makedirs(results_root, exist_ok=True)

    cmd_files = sorted(glob(os.path.join(commands_dir, "*.txt")))
    if not cmd_files:
        raise RuntimeError("No command files found")

    for cmd_path in cmd_files:
        cmd_id = Path(cmd_path).stem
        out_dir = os.path.join(results_root, cmd_id)
        plots_dir = os.path.join(out_dir, "plots")
        os.makedirs(plots_dir, exist_ok=True)

        text = Path(cmd_path).read_text()
        plan = parse_flight_plan(text)

        traj = trajectory_planner(
            waypoints=plan.waypoints,
            waypoint_times=plan.waypoint_times,
            sample_rate=float(params["sample_rate"]),
            modes=plan.modes,
            gravity=float(params["gravity"]),
            accel_limit_up=float(params["accel_limit_up"]),
            accel_limit_down=float(params["accel_limit_down"]),
            accel_limit_horiz=float(params["accel_limit_horiz"]),
        )

        np.save(os.path.join(out_dir, "planned_trajectory.npy"), traj.state)

        mode = plan.modes[0] if plan.modes else "hover"
        gains, actual, metrics = tune_for_command(traj.state, traj.time, mode, params)

        np.save(os.path.join(out_dir, "actual_trajectory.npy"), actual)

        with open(os.path.join(out_dir, "metrics_3d.json"), "w") as f:
            json.dump(metrics, f, indent=2)

        with open(os.path.join(out_dir, "tuning_results.json"), "w") as f:
            json.dump(_gains_to_jsonable(gains), f, indent=2)

        plot_results(actual, traj.state, traj.time, plots_dir)

    # Final completeness check
    required = [
        "metrics_3d.json",
        "tuning_results.json",
        "planned_trajectory.npy",
        "actual_trajectory.npy",
        os.path.join("plots", "desired_vs_actual.png"),
        os.path.join("plots", "errors.png"),
        os.path.join("plots", "cumulative_errors.png"),
    ]

    missing = []
    for cmd_path in cmd_files:
        cmd_id = Path(cmd_path).stem
        out_dir = os.path.join(results_root, cmd_id)
        for rel in required:
            p = os.path.join(out_dir, rel)
            if not os.path.exists(p):
                missing.append(p)

    if missing:
        raise RuntimeError("Missing required outputs:\n" + "\n".join(missing))


if __name__ == "__main__":
    run_all()
