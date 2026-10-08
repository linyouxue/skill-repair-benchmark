from __future__ import annotations

import glob
import json
import os
from dataclasses import asdict
from typing import Dict, Tuple

import numpy as np
import yaml

from flight_plan_parser import parse_flight_plan
from plot_quadrotor import plot_quadrotor
from simulator import Gains, simulate
from stepinfo_3d import stepinfo_3d
from trajectory_planner import trajectory_planner


def _validate_planned_accel(params: dict, planned: np.ndarray):
    up = float(params["accel_limit_up"])
    down = float(params["accel_limit_down"])
    horiz = float(params["accel_limit_horiz"])

    acc = planned[12:15, :]
    if np.any(acc[2, :] > up + 1e-9):
        raise ValueError("Planned trajectory exceeds accel_limit_up")
    if np.any(acc[2, :] < -down - 1e-9):
        raise ValueError("Planned trajectory exceeds accel_limit_down")

    axy = np.linalg.norm(acc[0:2, :], axis=0)
    if np.any(axy > horiz + 1e-9):
        raise ValueError("Planned trajectory exceeds accel_limit_horiz")


def _evaluate(params: dict, desired: np.ndarray, gains: Gains):
    actual = simulate(params, desired, gains)
    err = np.linalg.norm(actual[0:3, :] - desired[0:3, :], axis=0)
    max_err = float(np.max(err))

    dt = 1.0 / float(params["sample_rate"])
    t = np.arange(desired.shape[1]) * dt
    target = desired[0:3, -1]
    metrics = stepinfo_3d(actual[0:3, :], target, t, settling_threshold=0.02)

    # Objective: prioritize max error, then SSE and overshoot.
    score = max_err + 0.2 * float(metrics["SteadyStateError"]) + 0.01 * float(metrics["Overshoot_pct"])
    return score, max_err, metrics, actual


def tune(params: dict, desired: np.ndarray):
    # Small deterministic sweep; fast enough for this benchmark.
    kxy_list = [3.0, 5.0]
    kz_list = [6.0, 9.0]
    dxy_list = [2.0, 3.0]
    dz_list = [3.0, 5.0]

    kp_att = np.array([220.0, 220.0, 120.0])
    ki_att = np.array([0.0, 0.0, 0.0])
    kd_att = np.array([35.0, 35.0, 15.0])

    best = None
    best_payload = None

    for kxy in kxy_list:
        for kz in kz_list:
            for dxy in dxy_list:
                for dz in dz_list:
                    gains = Gains(
                        kp_pos=np.array([kxy, kxy, kz]),
                        ki_pos=np.array([0.0, 0.0, 0.0]),
                        kd_pos=np.array([dxy, dxy, dz]),
                        kp_att=kp_att,
                        ki_att=ki_att,
                        kd_att=kd_att,
                    )

                    score, max_err, metrics, actual = _evaluate(params, desired, gains)

                    payload = (score, max_err, metrics, gains, actual)
                    if best is None or score < best:
                        best = score
                        best_payload = payload

                    # Early accept if strict tracking is achieved and step metrics pass.
                    if (
                        max_err < 0.05
                        and float(metrics["SteadyStateError"]) < 0.05
                        and float(metrics["Overshoot_pct"]) < 5.0
                    ):
                        return gains, metrics, actual

    assert best_payload is not None
    _, _, metrics, gains, actual = best_payload
    return gains, metrics, actual


def main():
    params = yaml.safe_load(open("/root/system_params.yaml"))
    sample_rate = float(params["sample_rate"])

    os.makedirs("/root/results", exist_ok=True)

    for cmd_path in sorted(glob.glob("/root/commands/*.txt")):
        label = os.path.splitext(os.path.basename(cmd_path))[0]
        out_dir = os.path.join("/root/results", label)
        os.makedirs(out_dir, exist_ok=True)

        text = open(cmd_path).read().strip()
        waypoints, waypoint_times, modes = parse_flight_plan(text)

        time_final = float(waypoint_times[-1])
        extra_hold = 2.0
        max_iter = int(np.ceil((time_final + extra_hold) * sample_rate)) + 1

        desired = trajectory_planner(waypoints, max_iter, waypoint_times, sample_rate, modes)
        _validate_planned_accel(params, desired)

        np.save(os.path.join(out_dir, "planned_trajectory.npy"), desired)

        gains, metrics, actual = tune(params, desired)

        np.save(os.path.join(out_dir, "actual_trajectory.npy"), actual)

        mode = modes[0] if modes else "hover"
        metrics_out = {"mode": mode, **metrics}
        with open(os.path.join(out_dir, "metrics_3d.json"), "w") as f:
            json.dump(metrics_out, f, indent=2)

        tuning_out = {
            "kp_pos": [float(x) for x in gains.kp_pos],
            "ki_pos": [float(x) for x in gains.ki_pos],
            "kd_pos": [float(x) for x in gains.kd_pos],
            "kp_att": [float(x) for x in gains.kp_att],
            "ki_att": [float(x) for x in gains.ki_att],
            "kd_att": [float(x) for x in gains.kd_att],
        }
        with open(os.path.join(out_dir, "tuning_results.json"), "w") as f:
            json.dump(tuning_out, f, indent=2)

        dt = 1.0 / sample_rate
        time_vec = np.arange(max_iter) * dt
        plot_quadrotor(actual, desired, time_vec, save_dir=os.path.join(out_dir, "plots"))


if __name__ == "__main__":
    main()
