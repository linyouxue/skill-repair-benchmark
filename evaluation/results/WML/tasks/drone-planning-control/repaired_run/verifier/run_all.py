from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from typing import Dict, List, Tuple

import numpy as np

from controllers import Gains
from flight_plan_parser import parse_flight_plan
from motor_dynamics import simulate_trajectory
from plot_quadrotor import plot_quadrotor
from stepinfo_3d import stepinfo_3d
from system_params import SystemParams, load_system_params
from trajectory_planner import trajectory_planner


def _mode_from_text(text: str) -> str:
    for line in text.splitlines():
        s = line.strip().lower()
        if not s:
            continue
        if s.startswith("take off") or s.startswith("takeoff"):
            return "takeoff"
        if s.startswith("hover"):
            return "hover"
        if s.startswith("land"):
            return "land"
        if s.startswith("fly"):
            return "fly"
    return "unknown"


def _check_planned_limits(planned: np.ndarray, params: SystemParams) -> None:
    az = planned[14, :]
    axy = np.linalg.norm(planned[12:14, :], axis=0)

    if np.any(az > params.accel_limit_up + 1e-8):
        raise ValueError("planned_trajectory violates accel_limit_up")
    if np.any(az < -params.accel_limit_down - 1e-8):
        raise ValueError("planned_trajectory violates accel_limit_down")
    if np.any(axy > params.accel_limit_horiz + 1e-8):
        raise ValueError("planned_trajectory violates accel_limit_horiz")


def _candidate_gains() -> List[Gains]:
    """Small, fast gain set (per-command selection) to keep runtime reasonable."""

    # Keep Ki at 0 to avoid windup and to maintain strict per-timestep bounds.
    ki_pos = np.array([0.0, 0.0, 0.0])
    ki_att = np.array([0.0, 0.0, 0.0])

    pos_sets = [
        # baseline
        (np.array([6.0, 6.0, 10.0]), np.array([5.0, 5.0, 6.0])),
        # slightly softer
        (np.array([4.0, 4.0, 8.0]), np.array([3.0, 3.0, 5.0])),
        # more aggressive
        (np.array([8.0, 8.0, 14.0]), np.array([7.0, 7.0, 8.0])),
        # strong vertical, moderate horizontal
        (np.array([6.0, 6.0, 16.0]), np.array([5.0, 5.0, 9.0])),
    ]

    att_sets = [
        (np.array([220.0, 220.0, 80.0]), np.array([25.0, 25.0, 20.0])),
        (np.array([180.0, 180.0, 60.0]), np.array([18.0, 18.0, 16.0])),
        (np.array([300.0, 300.0, 100.0]), np.array([35.0, 35.0, 25.0])),
    ]

    cands: List[Gains] = []
    for kp_pos, kd_pos in pos_sets:
        for kp_att, kd_att in att_sets:
            cands.append(
                Gains(
                    kp_pos=kp_pos,
                    ki_pos=ki_pos,
                    kd_pos=kd_pos,
                    kp_att=kp_att,
                    ki_att=ki_att,
                    kd_att=kd_att,
                )
            )

    return cands


def _score_result(planned: np.ndarray, sim_max_err: float, metrics: Dict[str, float]) -> float:
    # Hard constraints handled elsewhere.
    # Prefer smaller peak error and faster settling.
    return (
        1000.0 * sim_max_err
        + 0.5 * metrics["SettlingTime"]
        + 0.2 * metrics["RiseTime"]
        + 0.1 * metrics["Overshoot_pct"]
        + 100.0 * metrics["SteadyStateError"]
    )


def tune_for_command(command_text: str, label: str, params: SystemParams) -> Tuple[Gains, np.ndarray, np.ndarray, np.ndarray, Dict[str, float]]:
    waypoints, waypoint_times, modes = parse_flight_plan(command_text)
    t_final = float(waypoint_times[-1])
    max_iter = int(np.round(t_final * params.sample_rate)) + 1

    planned = trajectory_planner(waypoints, max_iter, waypoint_times, params.sample_rate, modes, params)
    _check_planned_limits(planned, params)

    t = params.dt * np.arange(max_iter)
    target = waypoints[0:3, -1]

    best = None

    for gains in _candidate_gains():
        sim = simulate_trajectory(planned, params, gains)
        pos_err = np.linalg.norm(sim.actual[0:3, :].T - planned[0:3, :].T, axis=1)
        max_err = float(np.max(pos_err))

        metrics = stepinfo_3d(sim.actual[0:3, :], target, t, settling_threshold=0.02)
        ok = (
            metrics["SteadyStateError"] < 0.05
            and metrics["Overshoot_pct"] < 5.0
            and max_err < 0.05
        )

        score = _score_result(planned, max_err, metrics)

        if best is None:
            best = (ok, score, gains, sim)
            continue

        best_ok, best_score, *_ = best
        # Prefer feasible; otherwise lowest score.
        if ok and not best_ok:
            best = (ok, score, gains, sim)
        elif ok == best_ok and score < best_score:
            best = (ok, score, gains, sim)

    assert best is not None
    _, _, best_gains, best_sim = best

    metrics = stepinfo_3d(best_sim.actual[0:3, :], target, t, settling_threshold=0.02)
    mode = modes[0] if modes else _mode_from_text(command_text)
    metrics_out = {
        "mode": mode,
        "RiseTime": float(metrics["RiseTime"]),
        "SettlingTime": float(metrics["SettlingTime"]),
        "Overshoot_pct": float(metrics["Overshoot_pct"]),
        "SteadyStateError": float(metrics["SteadyStateError"]),
    }

    return best_gains, planned, best_sim.actual, best_sim.time, metrics_out


def write_outputs(label: str, out_dir: str, gains: Gains, planned: np.ndarray, actual: np.ndarray, t: np.ndarray, metrics: Dict[str, float]):
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(out_dir, "metrics_3d.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    tuning = {
        "kp_pos": [float(x) for x in gains.kp_pos],
        "ki_pos": [float(x) for x in gains.ki_pos],
        "kd_pos": [float(x) for x in gains.kd_pos],
        "kp_att": [float(x) for x in gains.kp_att],
        "ki_att": [float(x) for x in gains.ki_att],
        "kd_att": [float(x) for x in gains.kd_att],
    }

    with open(os.path.join(out_dir, "tuning_results.json"), "w") as f:
        json.dump(tuning, f, indent=2)

    np.save(os.path.join(out_dir, "planned_trajectory.npy"), planned)
    np.save(os.path.join(out_dir, "actual_trajectory.npy"), actual)

    plot_quadrotor(actual, planned, t, save_dir=os.path.join(out_dir, "plots"))


def run_all(commands_dir: str = "/root/commands", results_dir: str = "/root/results", *, only: List[str] | None = None):
    params = load_system_params()
    os.makedirs(results_dir, exist_ok=True)

    files = sorted([f for f in os.listdir(commands_dir) if f.endswith(".txt")])
    for fname in files:
        label = os.path.splitext(fname)[0]
        if only and label not in only:
            continue

        with open(os.path.join(commands_dir, fname), "r") as f:
            text = f.read()

        gains, planned, actual, t, metrics = tune_for_command(text, label, params)
        out_dir = os.path.join(results_dir, label)
        write_outputs(label, out_dir, gains, planned, actual, t, metrics)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--commands_dir", default="/root/commands")
    ap.add_argument("--results_dir", default="/root/results")
    ap.add_argument("--only", nargs="*", help="Only generate results for these labels (e.g. 001 017)")
    args = ap.parse_args()

    run_all(args.commands_dir, args.results_dir, only=args.only)


if __name__ == "__main__":
    main()
