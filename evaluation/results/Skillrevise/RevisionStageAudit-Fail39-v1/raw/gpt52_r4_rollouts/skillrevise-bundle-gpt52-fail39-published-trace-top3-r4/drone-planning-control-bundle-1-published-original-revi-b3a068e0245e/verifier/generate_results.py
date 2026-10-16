from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from drone_sim.controllers import PIDGains
from drone_sim.flight_plan_parser import parse_command
from drone_sim.params import load_params
from drone_sim.plot_quadrotor import plot_quadrotor
from drone_sim.simulate import simulate_closed_loop
from drone_sim.stepinfo_3d import stepinfo_3d
from drone_sim.trajectory_planner import plan_state_trajectory


def _gains_to_json(g: PIDGains) -> dict:
    return {
        "kp_pos": [float(x) for x in g.kp_pos],
        "ki_pos": [float(x) for x in g.ki_pos],
        "kd_pos": [float(x) for x in g.kd_pos],
        "kp_att": [float(x) for x in g.kp_att],
        "ki_att": [float(x) for x in g.ki_att],
        "kd_att": [float(x) for x in g.kd_att],
    }


def _evaluate(actual: np.ndarray, planned: np.ndarray, time_vec: np.ndarray, target: np.ndarray) -> dict:
    pos_err = np.linalg.norm(actual[0:3, :] - planned[0:3, :], axis=0)
    max_err = float(np.max(pos_err))
    metrics = stepinfo_3d(actual[0:3, :], target, time_vec, settling_threshold=0.02)
    return {
        "max_pos_err": max_err,
        "metrics": metrics,
        "pos_err": pos_err,
    }


def tune_for_command(mode: str, planned: np.ndarray, time_vec: np.ndarray, params) -> tuple[PIDGains, np.ndarray, dict]:
    if mode in {"takeoff", "land", "hover"}:
        kp_pos_base = np.array([6.0, 6.0, 22.0])
        kd_pos_base = np.array([4.5, 4.5, 14.0])
        ki_pos_base = np.array([0.0, 0.0, 0.2])
    else:
        kp_pos_base = np.array([12.0, 12.0, 20.0])
        kd_pos_base = np.array([8.0, 8.0, 12.0])
        ki_pos_base = np.array([0.0, 0.0, 0.1])

    kp_att_base = np.array([160.0, 160.0, 90.0])
    kd_att_base = np.array([18.0, 18.0, 10.0])
    ki_att_base = np.array([0.0, 0.0, 0.0])

    pos_scales = [0.8, 1.0, 1.2, 1.5]
    att_scales = [0.8, 1.0, 1.2]
    ki_z_scales = [0.0, 1.0]

    best = None

    target = planned[0:3, -1]

    for s_pos in pos_scales:
        for s_att in att_scales:
            for s_ki in ki_z_scales:
                gains = PIDGains(
                    kp_pos=kp_pos_base * s_pos,
                    kd_pos=kd_pos_base * s_pos,
                    ki_pos=ki_pos_base * s_ki,
                    kp_att=kp_att_base * s_att,
                    kd_att=kd_att_base * s_att,
                    ki_att=ki_att_base,
                )

                actual = simulate_closed_loop(planned, time_vec, gains, params)
                ev = _evaluate(actual, planned, time_vec, target)

                ok_err = bool(np.all(ev["pos_err"] < 0.05 + 1e-12))
                ok_metrics = bool(ev["metrics"]["SteadyStateError"] < 0.05 and ev["metrics"]["Overshoot_pct"] < 5.0)

                score = ev["max_pos_err"] + 2.0 * ev["metrics"]["SteadyStateError"] + 0.02 * ev["metrics"]["Overshoot_pct"]
                feasible = ok_err and ok_metrics

                cand = {
                    "gains": gains,
                    "actual": actual,
                    "ev": ev,
                    "score": score,
                    "feasible": feasible,
                }

                if best is None:
                    best = cand
                    continue

                if cand["feasible"] and not best["feasible"]:
                    best = cand
                elif cand["feasible"] == best["feasible"] and cand["score"] < best["score"]:
                    best = cand

    assert best is not None
    return best["gains"], best["actual"], best["ev"]["metrics"]


def main() -> None:
    params = load_params("/root/system_params.yaml")

    commands_dir = Path("/root/commands")
    out_root = Path("/root/results")
    out_root.mkdir(parents=True, exist_ok=True)

    for cmd_path in sorted(commands_dir.glob("*.txt")):
        cmd_id = cmd_path.stem
        text = cmd_path.read_text().strip()
        plan = parse_command(text)

        planned, time_vec = plan_state_trajectory(plan, params)
        gains, actual, metrics = tune_for_command(plan.mode, planned, time_vec, params)

        out_dir = out_root / cmd_id
        plots_dir = out_dir / "plots"
        out_dir.mkdir(parents=True, exist_ok=True)
        plots_dir.mkdir(parents=True, exist_ok=True)

        np.save(out_dir / "planned_trajectory.npy", planned)
        np.save(out_dir / "actual_trajectory.npy", actual)

        plot_quadrotor(actual, planned, time_vec, plots_dir)

        metrics_out = {"mode": plan.mode, **metrics}
        (out_dir / "metrics_3d.json").write_text(json.dumps(metrics_out, indent=2) + "\n")
        (out_dir / "tuning_results.json").write_text(json.dumps(_gains_to_json(gains), indent=2) + "\n")

        pos_err = np.linalg.norm(actual[0:3, :] - planned[0:3, :], axis=0)
        max_err = float(np.max(pos_err))
        ok = (
            float(metrics["SteadyStateError"]) < 0.05
            and float(metrics["Overshoot_pct"]) < 5.0
            and bool(np.all(pos_err < 0.05 + 1e-12))
        )

        print(
            f"{cmd_id} mode={plan.mode} ok={ok} max_err={max_err:.4f} "
            f"sse={metrics['SteadyStateError']:.4f} ov={metrics['Overshoot_pct']:.2f}%"
        )


if __name__ == "__main__":
    main()
