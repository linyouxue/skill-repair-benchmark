from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

from controllers import (
    DesiredState,
    State,
    attitude_controller,
    attitude_planner,
    make_attitude_integral,
    make_position_integral,
    position_controller,
)
from flight_plan_parser import parse_flight_plan
from plot_quadrotor import plot_trajectories
from quad_dynamics import mix_to_rpm, rk4_step, state_derivative
from stepinfo_3d import stepinfo_3d
from system_params import load_params
from trajectory_planner import trajectory_planner


@dataclass
class Gains:
    kp_pos: np.ndarray
    ki_pos: np.ndarray
    kd_pos: np.ndarray
    kp_att: np.ndarray
    ki_att: np.ndarray
    kd_att: np.ndarray


def _initial_state_from_plan(waypoints: np.ndarray, params: dict) -> np.ndarray:
    s = np.zeros(16, dtype=float)
    s[0:3] = waypoints[0:3, 0]
    s[3:6] = 0.0
    s[6:9] = 0.0
    s[9:12] = 0.0

    cT = float(params["thrust_coefficient"])
    m = float(params["mass"])
    g = float(params["gravity"])
    rpm_hover = float(np.sqrt((m * g) / (4.0 * cT)))
    rpm_hover = float(np.clip(rpm_hover, float(params["rpm_min"]), float(params["rpm_max"])))
    s[12:16] = rpm_hover
    return s


def _fill_desired_attitude(traj: np.ndarray, params: dict) -> np.ndarray:
    out = np.asarray(traj, dtype=float).copy()
    for k in range(out.shape[1]):
        desired = DesiredState(
            pos=out[0:3, k],
            vel=out[3:6, k],
            rot=out[6:9, k],
            omega=out[9:12, k],
            acc=out[12:15, k],
        )
        rot, omega = attitude_planner(desired, params)
        out[6:9, k] = rot
        out[9:12, k] = omega
    return out


def _check_planned_accel_limits(traj: np.ndarray, params: dict) -> None:
    acc = np.asarray(traj[12:15, :], dtype=float)

    axy = np.linalg.norm(acc[0:2, :].T, axis=1)
    if np.any(axy > float(params["accel_limit_horiz"]) + 1e-9):
        raise ValueError("Planned trajectory violates horizontal accel limit")

    if np.any(acc[2, :] > float(params["accel_limit_up"]) + 1e-9):
        raise ValueError("Planned trajectory violates upward accel limit")

    if np.any(acc[2, :] < -float(params["accel_limit_down"]) - 1e-9):
        raise ValueError("Planned trajectory violates downward accel limit")


def simulate(params: dict, traj_des: np.ndarray, gains: Gains, init_state: np.ndarray) -> np.ndarray:
    dt = 1.0 / float(params["sample_rate"])
    n = traj_des.shape[1]

    pos_int = make_position_integral()
    att_int = make_attitude_integral()

    state = np.asarray(init_state, dtype=float).copy()
    actual = np.zeros((15, n), dtype=float)

    rpm_des_prev = state[12:16].copy()

    for k in range(n - 1):
        current = State(pos=state[0:3], vel=state[3:6], rot=state[6:9], omega=state[9:12])
        desired = DesiredState(
            pos=traj_des[0:3, k],
            vel=traj_des[3:6, k],
            rot=traj_des[6:9, k],
            omega=traj_des[9:12, k],
            acc=traj_des[12:15, k],
        )

        F_cmd, acc_cmd = position_controller(
            current,
            desired,
            params,
            pos_int,
            gains.kp_pos,
            gains.ki_pos,
            gains.kd_pos,
        )

        desired_for_att = DesiredState(
            pos=desired.pos,
            vel=desired.vel,
            rot=desired.rot.copy(),
            omega=desired.omega.copy(),
            acc=acc_cmd,
        )
        rot_des, omega_des = attitude_planner(desired_for_att, params)
        desired_for_att.rot = rot_des
        desired_for_att.omega = omega_des

        M_cmd = attitude_controller(
            current,
            desired_for_att,
            params,
            att_int,
            gains.kp_att,
            gains.ki_att,
            gains.kd_att,
        )

        rpm_des = mix_to_rpm(params, F_cmd, M_cmd)
        rpm_des_prev = rpm_des

        # Store actual sample before integration.
        sdot = state_derivative(params, state, rpm_des)
        actual[0:3, k] = state[0:3]
        actual[3:6, k] = state[3:6]
        actual[6:9, k] = state[6:9]
        actual[9:12, k] = state[9:12]
        actual[12:15, k] = sdot[3:6]

        state = rk4_step(params, state, rpm_des, dt)

    # Last sample
    sdot = state_derivative(params, state, rpm_des_prev)
    actual[0:3, -1] = state[0:3]
    actual[3:6, -1] = state[3:6]
    actual[6:9, -1] = state[6:9]
    actual[9:12, -1] = state[9:12]
    actual[12:15, -1] = sdot[3:6]

    return actual


def _score(traj_des: np.ndarray, traj_act: np.ndarray, time_vec: np.ndarray, mode: str) -> Tuple[float, Dict[str, float]]:
    err = traj_act[0:3, :] - traj_des[0:3, :]
    dist_err = np.linalg.norm(err.T, axis=1)
    max_err = float(np.max(dist_err))

    target = traj_des[0:3, -1]
    metrics = stepinfo_3d(traj_act[0:3, :], target, time_vec, settling_threshold=0.02)

    sse = float(metrics["SteadyStateError"])
    overshoot = float(metrics["Overshoot_pct"])

    penalty = 0.0
    penalty += 1000.0 * max(0.0, max_err - 0.05)
    penalty += 1000.0 * max(0.0, sse - 0.05)
    penalty += 200.0 * max(0.0, overshoot - 5.0)

    cost = max_err + 0.5 * sse + 0.02 * float(metrics["SettlingTime"]) + 0.01 * overshoot + penalty
    return cost, metrics


def tune(params: dict, traj_des: np.ndarray, time_vec: np.ndarray, init_state: np.ndarray, mode: str) -> Tuple[Gains, np.ndarray, Dict[str, float]]:
    base = Gains(
        kp_pos=np.array([6.0, 6.0, 10.0]),
        ki_pos=np.array([0.05, 0.05, 0.08]),
        kd_pos=np.array([5.0, 5.0, 7.0]),
        kp_att=np.array([260.0, 260.0, 120.0]),
        ki_att=np.array([0.0, 0.0, 0.2]),
        kd_att=np.array([25.0, 25.0, 12.0]),
    )

    rng = np.random.default_rng(0)

    candidates: List[Gains] = []

    # Deterministic coarse grid scales
    for s_pos in [0.6, 0.8, 1.0, 1.2, 1.5]:
        for s_att in [0.6, 0.8, 1.0, 1.2]:
            for s_d in [0.7, 1.0, 1.3]:
                candidates.append(
                    Gains(
                        kp_pos=base.kp_pos * s_pos,
                        ki_pos=base.ki_pos,
                        kd_pos=base.kd_pos * s_d,
                        kp_att=base.kp_att * s_att,
                        ki_att=base.ki_att,
                        kd_att=base.kd_att * s_d,
                    )
                )

    # Add a few random perturbations
    for _ in range(25):
        sp = float(rng.uniform(0.5, 1.8))
        sa = float(rng.uniform(0.5, 1.6))
        sd = float(rng.uniform(0.6, 1.6))
        candidates.append(
            Gains(
                kp_pos=base.kp_pos * sp,
                ki_pos=base.ki_pos * float(rng.uniform(0.5, 1.5)),
                kd_pos=base.kd_pos * sd,
                kp_att=base.kp_att * sa,
                ki_att=base.ki_att,
                kd_att=base.kd_att * sd,
            )
        )

    best_cost = float("inf")
    best_gains = base
    best_act = None
    best_metrics: Dict[str, float] = {}

    for gains in candidates:
        act = simulate(params, traj_des, gains, init_state)
        cost, metrics = _score(traj_des, act, time_vec, mode)
        if cost < best_cost:
            best_cost = cost
            best_gains = gains
            best_act = act
            best_metrics = metrics

        # Early stop if constraints are satisfied well
        if (
            best_metrics
            and best_metrics.get("SteadyStateError", 1e9) < 0.03
            and best_metrics.get("Overshoot_pct", 1e9) < 3.0
        ):
            err = np.linalg.norm((best_act[0:3, :] - traj_des[0:3, :]).T, axis=1)
            if float(np.max(err)) < 0.04:
                break

    assert best_act is not None
    return best_gains, best_act, best_metrics


def main() -> None:
    params = load_params("/root/system_params.yaml")

    commands_dir = Path("/root/commands")
    out_root = Path("/root/results")
    os.makedirs(out_root, exist_ok=True)

    for cmd_path in sorted(commands_dir.glob("*.txt")):
        label = cmd_path.stem
        text = cmd_path.read_text(encoding="utf-8")
        waypoints, waypoint_times, modes = parse_flight_plan(text)
        mode = modes[0] if modes else "hover"

        time_final = float(waypoint_times[-1])
        sr = float(params["sample_rate"])
        max_iter = int(np.round(time_final * sr)) + 1
        time_vec = np.arange(max_iter, dtype=float) / sr

        traj = trajectory_planner(waypoints, max_iter, waypoint_times, sr, modes)
        traj = _fill_desired_attitude(traj, params)
        _check_planned_accel_limits(traj, params)

        init_state = _initial_state_from_plan(waypoints, params)
        best_gains, actual, metrics = tune(params, traj, time_vec, init_state, mode)

        pos_err = np.linalg.norm((actual[0:3, :] - traj[0:3, :]).T, axis=1)
        max_err = float(np.max(pos_err))

        # Write outputs
        out_dir = out_root / label
        plots_dir = out_dir / "plots"
        os.makedirs(plots_dir, exist_ok=True)

        np.save(out_dir / "planned_trajectory.npy", traj)
        np.save(out_dir / "actual_trajectory.npy", actual)

        metrics_out = {"mode": mode, **metrics}
        with open(out_dir / "metrics_3d.json", "w", encoding="utf-8") as f:
            json.dump(metrics_out, f, indent=2)

        tuning_out = {
            "kp_pos": best_gains.kp_pos.tolist(),
            "ki_pos": best_gains.ki_pos.tolist(),
            "kd_pos": best_gains.kd_pos.tolist(),
            "kp_att": best_gains.kp_att.tolist(),
            "ki_att": best_gains.ki_att.tolist(),
            "kd_att": best_gains.kd_att.tolist(),
        }
        with open(out_dir / "tuning_results.json", "w", encoding="utf-8") as f:
            json.dump(tuning_out, f, indent=2)

        plot_trajectories(actual, traj, time_vec, plots_dir)

        # Basic console status
        print(
            f"{label} mode={mode:<7} max_err={max_err:.4f} SSE={metrics['SteadyStateError']:.4f} OS={metrics['Overshoot_pct']:.2f}%"
        )


if __name__ == "__main__":
    main()
