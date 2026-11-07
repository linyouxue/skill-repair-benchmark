from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Tuple

import numpy as np

from controllers import (
    PIDGains,
    attitude_controller,
    attitude_planner_from_accel,
    default_gains_for_mode,
    make_attitude_integral,
    make_position_integral,
    position_controller,
)
from params import load_system_params
from plot_quadrotor import plot_quadrotor
from quadrotor import initial_state, mix_to_rpm, step_dynamics
from stepinfo_3d import stepinfo_3d
from trajectory_planner import plan_point_to_point


def _parse_single_command(line: str) -> Tuple[str, np.ndarray, np.ndarray, float]:
    line = line.strip()
    if not line:
        raise ValueError("Empty command")

    import re

    m = re.match(r"^Take off to\s+([0-9.]+)\s+m height in\s+([0-9.]+)\s+seconds$", line, re.IGNORECASE)
    if m:
        h, T = float(m.group(1)), float(m.group(2))
        return "takeoff", np.array([0.0, 0.0, 0.0]), np.array([0.0, 0.0, h]), T

    m = re.match(r"^Hover at\s+([0-9.]+)\s+m height for\s+([0-9.]+)\s+seconds$", line, re.IGNORECASE)
    if m:
        h, T = float(m.group(1)), float(m.group(2))
        p = np.array([0.0, 0.0, h])
        return "hover", p, p.copy(), T

    m = re.match(r"^Land from\s+([0-9.]+)\s+m height in\s+([0-9.]+)\s+seconds$", line, re.IGNORECASE)
    if m:
        h, T = float(m.group(1)), float(m.group(2))
        return "land", np.array([0.0, 0.0, h]), np.array([0.0, 0.0, 0.0]), T

    m = re.match(
        r"^Fly from\s*\(\s*([+-]?[0-9.]+)\s*,\s*([+-]?[0-9.]+)\s*,\s*([+-]?[0-9.]+)\s*\)\s*"
        r"to\s*\(\s*([+-]?[0-9.]+)\s*,\s*([+-]?[0-9.]+)\s*,\s*([+-]?[0-9.]+)\s*\)\s*in\s*([0-9.]+)\s*seconds$",
        line,
        re.IGNORECASE,
    )
    if m:
        p0 = np.array([float(m.group(1)), float(m.group(2)), float(m.group(3))], dtype=float)
        p1 = np.array([float(m.group(4)), float(m.group(5)), float(m.group(6))], dtype=float)
        T = float(m.group(7))
        return "fly", p0, p1, T

    raise ValueError(f"Unrecognized command: {line}")


def _simulate(state_des: np.ndarray, gains: PIDGains, params) -> np.ndarray:
    dt = 1.0 / params.sample_rate
    N = state_des.shape[1]

    state = initial_state(state_des[0:3, 0], params)
    pos_int = make_position_integral()
    att_int = make_attitude_integral()

    actual = np.zeros((15, N), dtype=float)
    acc_prev = np.zeros(3, dtype=float)

    for k in range(N):
        actual[0:3, k] = state.pos
        actual[3:6, k] = state.vel
        actual[6:9, k] = state.euler
        actual[9:12, k] = state.omega
        actual[12:15, k] = acc_prev

        if k == N - 1:
            break

        pos_des = state_des[0:3, k]
        vel_des = state_des[3:6, k]
        acc_des = state_des[12:15, k]
        yaw_des = float(state_des[8, k])

        a_cmd = position_controller(
            state.pos,
            state.vel,
            pos_des,
            vel_des,
            acc_des,
            pos_int,
            gains,
            params,
            dt,
        )

        euler_des, omega_des, thrust_des = attitude_planner_from_accel(a_cmd, yaw_des, params)
        moment_cmd = attitude_controller(
            state.euler,
            state.omega,
            euler_des,
            omega_des,
            att_int,
            gains,
            params,
            dt,
        )

        rpm_cmd = mix_to_rpm(float(thrust_des), moment_cmd, params)
        state, acc_prev = step_dynamics(state, rpm_cmd, params, dt)

    return actual


def _score(actual: np.ndarray, desired: np.ndarray) -> Dict[str, float]:
    err = actual[0:3, :] - desired[0:3, :]
    dist = np.linalg.norm(err, axis=0)
    return {
        "max_pos_err": float(np.max(dist)),
        "mean_pos_err": float(np.mean(dist)),
    }


def _gains_to_jsonable(g: PIDGains) -> Dict[str, list]:
    return {
        "kp_pos": [float(x) for x in g.kp_pos],
        "ki_pos": [float(x) for x in g.ki_pos],
        "kd_pos": [float(x) for x in g.kd_pos],
        "kp_att": [float(x) for x in g.kp_att],
        "ki_att": [float(x) for x in g.ki_att],
        "kd_att": [float(x) for x in g.kd_att],
    }


def tune_and_run(command_path: Path, out_dir: Path, params) -> None:
    cmd_text = command_path.read_text(encoding="utf-8").strip()
    mode, p0, p1, T = _parse_single_command(cmd_text)

    planned = plan_point_to_point(mode, p0, p1, T, params, yaw=0.0)

    base = default_gains_for_mode(mode)
    candidates = [0.9, 1.0, 1.15]

    best = None
    best_score = None
    best_actual = None

    for s in candidates:
        g = PIDGains(
            kp_pos=base.kp_pos * s,
            ki_pos=base.ki_pos,
            kd_pos=base.kd_pos * s,
            kp_att=base.kp_att,
            ki_att=base.ki_att,
            kd_att=base.kd_att,
        )
        actual = _simulate(planned.state_des, g, params)
        score = _score(actual, planned.state_des)

        ok = (
            score["max_pos_err"] < 0.05
            and float(np.linalg.norm(actual[0:3, -1] - planned.state_des[0:3, -1])) < 0.05
        )

        if best is None or score["max_pos_err"] < best_score["max_pos_err"]:
            best = g
            best_score = score
            best_actual = actual

        if ok:
            best = g
            best_score = score
            best_actual = actual
            break

    assert best is not None and best_actual is not None

    metrics = stepinfo_3d(
        best_actual[0:3, :],
        planned.state_des[0:3, -1],
        planned.time,
        settling_threshold=0.02,
    )
    metrics_out = {"mode": mode, **metrics}

    out_dir.mkdir(parents=True, exist_ok=True)
    plots_dir = out_dir / "plots"

    np.save(out_dir / "planned_trajectory.npy", planned.state_des)
    np.save(out_dir / "actual_trajectory.npy", best_actual)

    (out_dir / "metrics_3d.json").write_text(json.dumps(metrics_out, indent=2), encoding="utf-8")
    (out_dir / "tuning_results.json").write_text(json.dumps(_gains_to_jsonable(best), indent=2), encoding="utf-8")

    plot_quadrotor(best_actual, planned.state_des, planned.time, str(plots_dir), params)


def main() -> None:
    params = load_system_params("/root/system_params.yaml")

    commands_dir = Path("/root/commands")
    results_dir = Path("/root/results")
    results_dir.mkdir(parents=True, exist_ok=True)

    for cmd_path in sorted(commands_dir.glob("*.txt")):
        cmd_id = cmd_path.stem
        out_dir = results_dir / cmd_id
        tune_and_run(cmd_path, out_dir, params)


if __name__ == "__main__":
    main()
