"""Run every command in /root/commands and write its result directory."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from drone_simulation import (
    FlightPlanParser,
    gains_for_simulation,
    load_params,
    plot_quadrotor,
    simulate,
    stepinfo_3d,
    trajectory_planner,
    write_json,
)


def run_command(command_path: Path, results_root: Path, params: dict) -> dict:
    parser = FlightPlanParser()
    parser.add_line(command_path.read_text(encoding="utf-8"))
    plan = parser.plan()
    duration = float(plan.waypoint_times[-1])
    max_iter = int(round(duration * params["sample_rate"])) + 1
    planned = trajectory_planner(
        plan.waypoints,
        max_iter,
        plan.waypoint_times,
        params["sample_rate"],
        plan.modes,
        params,
    )
    gains = gains_for_simulation()
    actual = simulate(planned, params, gains)
    label = command_path.stem
    out_dir = results_root / label
    out_dir.mkdir(parents=True, exist_ok=True)
    np.save(out_dir / "planned_trajectory.npy", planned)
    np.save(out_dir / "actual_trajectory.npy", actual)
    time = np.arange(max_iter, dtype=float) / params["sample_rate"]
    metrics = stepinfo_3d(actual[0:3], planned[0:3], time, settling_threshold=0.02)
    write_json(out_dir / "metrics_3d.json", {"mode": plan.modes[-1], **metrics})
    write_json(out_dir / "tuning_results.json", gains)
    plot_quadrotor(actual, planned, time, out_dir / "plots")
    position_error = np.linalg.norm(actual[0:3] - planned[0:3], axis=0)
    return {
        "label": label,
        "mode": plan.modes[-1],
        "samples": max_iter,
        "max_position_error": float(position_error.max()),
        **metrics,
    }


def main() -> None:
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("--commands", type=Path, default=Path("/root/commands"))
    argument_parser.add_argument("--results", type=Path, default=Path("/root/results"))
    argument_parser.add_argument("--only", nargs="*", help="command labels such as 001 017")
    args = argument_parser.parse_args()
    params = load_params()
    selected = set(args.only or [])
    command_paths = sorted(args.commands.glob("*.txt"))
    if selected:
        command_paths = [path for path in command_paths if path.stem in selected]
    if not command_paths:
        raise SystemExit("no command files selected")
    summaries = []
    for command_path in command_paths:
        summary = run_command(command_path, args.results, params)
        summaries.append(summary)
        print(
            f"{summary['label']}: max_err={summary['max_position_error']:.5f} m, "
            f"final={summary['SteadyStateError']:.5f} m, "
            f"overshoot={summary['Overshoot_pct']:.3f}%"
        )
    print(f"Wrote {len(summaries)} command result directories to {args.results}")


if __name__ == "__main__":
    main()
