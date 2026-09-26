from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from drone_sim.controllers import PIDGains
from drone_sim.flight_plan_parser import parse_flight_plan
from drone_sim.metrics import stepinfo_3d
from drone_sim.params import load_params
from drone_sim.plotting import plot_results
from drone_sim.simulate import simulate_closed_loop
from drone_sim.trajectory_planner import trajectory_planner


COMMANDS_DIR = Path("/root/commands")
RESULTS_DIR = Path("/root/results")


def _as_list(x: np.ndarray) -> list[float]:
    return [float(v) for v in np.array(x, dtype=float).tolist()]


def _check_accel_limits(traj_des: np.ndarray, params) -> None:
    acc = traj_des[12:15, :]
    az = acc[2, :]
    if np.any(az > params.accel_limit_up + 1e-9):
        raise ValueError("Planned az exceeds accel_limit_up")
    if np.any(az < -params.accel_limit_down - 1e-9):
        raise ValueError("Planned az exceeds accel_limit_down")

    ah = np.linalg.norm(acc[0:2, :], axis=0)
    if np.any(ah > params.accel_limit_horiz + 1e-9):
        raise ValueError("Planned horizontal accel exceeds accel_limit_horiz")


def _evaluate(traj_des: np.ndarray, actual: np.ndarray, time_vec: np.ndarray, mode: str) -> tuple[dict, float, float]:
    pos_err = np.linalg.norm(actual[0:3, :] - traj_des[0:3, :], axis=0)
    max_pos_err = float(np.max(pos_err))

    pos_target = traj_des[0:3, -1]
    metrics = stepinfo_3d(actual[0:3, :], pos_target, time_vec, settling_threshold=0.02)

    # Cost: prioritize max per-step error, then steady-state error.
    cost = 1e6 * max(0.0, max_pos_err - 0.05) + 1e3 * metrics["SteadyStateError"] + 10.0 * metrics["Overshoot_pct"]

    metrics_out = {"mode": mode, **metrics}
    return metrics_out, cost, max_pos_err


def _generate_candidates(
    base: PIDGains,
    rng: np.random.Generator,
    n_random: int = 40,
    kp_scale: tuple[float, float] = (0.5, 2.5),
    kd_scale: tuple[float, float] = (0.5, 2.5),
) -> list[PIDGains]:
    cands = [base]

    def jitter(v: np.ndarray, lo: float, hi: float) -> np.ndarray:
        mult = rng.uniform(lo, hi, size=v.shape)
        return v * mult

    for _ in range(n_random):
        kp_pos = jitter(base.kp_pos, *kp_scale)
        kd_pos = jitter(base.kd_pos, *kd_scale)
        ki_pos = jitter(base.ki_pos, 0.0, 0.5)

        kp_att = jitter(base.kp_att, *kp_scale)
        kd_att = jitter(base.kd_att, *kd_scale)
        ki_att = jitter(base.ki_att, 0.0, 0.2)

        cands.append(
            PIDGains(
                kp_pos=kp_pos,
                ki_pos=ki_pos,
                kd_pos=kd_pos,
                kp_att=kp_att,
                ki_att=ki_att,
                kd_att=kd_att,
            )
        )

    return cands


def run_one(command_path: Path, params) -> None:
    label = command_path.stem
    out_dir = RESULTS_DIR / label
    plots_dir = out_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    text = command_path.read_text(encoding="utf-8")
    waypoints, waypoint_times, modes = parse_flight_plan(text)
    mode = modes[0] if modes else "unknown"

    planned = trajectory_planner(waypoints, waypoint_times, modes, params.sample_rate)
    traj_des = planned.state_des
    time_vec = planned.time

    _check_accel_limits(traj_des, params)

    base = PIDGains(
        kp_pos=np.array([6.0, 6.0, 14.0], dtype=float),
        ki_pos=np.array([0.01, 0.01, 0.03], dtype=float),
        kd_pos=np.array([4.5, 4.5, 8.0], dtype=float),
        kp_att=np.array([400.0, 400.0, 180.0], dtype=float),
        ki_att=np.array([0.0, 0.0, 0.0], dtype=float),
        kd_att=np.array([60.0, 60.0, 25.0], dtype=float),
    )

    rng = np.random.default_rng(int(label))
    candidates = _generate_candidates(base, rng)

    def pick_best(cands: list[PIDGains]):
        best_ok = None
        best_ok_cost = float("inf")
        best_ok_metrics = None
        best_ok_actual = None
        best_ok_max_err = None

        best_any = None
        best_any_cost = float("inf")
        best_any_metrics = None
        best_any_actual = None
        best_any_max_err = None

        for gains in cands:
            sim = simulate_closed_loop(params, traj_des, gains)
            metrics_out, cost, max_pos_err = _evaluate(traj_des, sim.actual, time_vec, mode)

            ok = (
                metrics_out["SteadyStateError"] < 0.05
                and metrics_out["Overshoot_pct"] < 5.0
                and max_pos_err < 0.05
            )

            if ok and cost < best_ok_cost:
                best_ok = gains
                best_ok_cost = cost
                best_ok_metrics = metrics_out
                best_ok_actual = sim.actual
                best_ok_max_err = max_pos_err

            if cost < best_any_cost:
                best_any = gains
                best_any_cost = cost
                best_any_metrics = metrics_out
                best_any_actual = sim.actual
                best_any_max_err = max_pos_err

        if best_ok is not None:
            return best_ok, best_ok_metrics, best_ok_actual, best_ok_max_err
        return best_any, best_any_metrics, best_any_actual, best_any_max_err

    best, best_metrics, best_actual, best_max_err = pick_best(candidates)

    # If no candidate satisfies the strict constraint, try a more aggressive set.
    if best_metrics is None or best_actual is None or best_max_err is None or best_max_err >= 0.05:
        aggressive = PIDGains(
            kp_pos=base.kp_pos * 2.0,
            ki_pos=base.ki_pos,
            kd_pos=base.kd_pos * 1.7,
            kp_att=base.kp_att * 2.0,
            ki_att=base.ki_att,
            kd_att=base.kd_att * 2.0,
        )
        candidates2 = _generate_candidates(aggressive, rng, n_random=80, kp_scale=(0.8, 2.8), kd_scale=(0.8, 2.8))
        best, best_metrics, best_actual, best_max_err = pick_best(candidates2)

    assert best is not None and best_metrics is not None and best_actual is not None and best_max_err is not None

    # Write artifacts.
    np.save(out_dir / "planned_trajectory.npy", traj_des)
    np.save(out_dir / "actual_trajectory.npy", best_actual)

    with open(out_dir / "metrics_3d.json", "w", encoding="utf-8") as f:
        json.dump(best_metrics, f, indent=2)

    tuning = {
        "kp_pos": _as_list(best.kp_pos),
        "ki_pos": _as_list(best.ki_pos),
        "kd_pos": _as_list(best.kd_pos),
        "kp_att": _as_list(best.kp_att),
        "ki_att": _as_list(best.ki_att),
        "kd_att": _as_list(best.kd_att),
    }
    with open(out_dir / "tuning_results.json", "w", encoding="utf-8") as f:
        json.dump(tuning, f, indent=2)

    plot_results(best_actual, traj_des, time_vec, plots_dir)

    # Fail fast if strict requirement not met.
    pos_err = np.linalg.norm(best_actual[0:3, :] - traj_des[0:3, :], axis=0)
    if not np.all(pos_err < 0.05):
        raise RuntimeError(f"{label}: per-step position error violates 0.05m, max={best_max_err:.4f}")


def main() -> None:
    params = load_params()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    command_files = sorted(COMMANDS_DIR.glob("*.txt"))
    if not command_files:
        raise RuntimeError(f"No command files found in {COMMANDS_DIR}")

    for p in command_files:
        run_one(p, params)

    # Completeness check.
    required = {
        "metrics_3d.json",
        "tuning_results.json",
        "planned_trajectory.npy",
        "actual_trajectory.npy",
    }
    for p in command_files:
        label = p.stem
        out_dir = RESULTS_DIR / label
        missing = [name for name in required if not (out_dir / name).exists()]
        missing += [
            str(out_dir / "plots" / img)
            for img in ["desired_vs_actual.png", "errors.png", "cumulative_errors.png"]
            if not (out_dir / "plots" / img).exists()
        ]
        if missing:
            raise RuntimeError(f"Missing outputs for {label}: {missing}")


if __name__ == "__main__":
    main()
