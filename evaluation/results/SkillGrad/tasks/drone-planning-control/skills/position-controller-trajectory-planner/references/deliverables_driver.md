# Deliverables driver: per-command pipeline + on-disk verification

Use this chapter when the harness grades based on files under a required results directory (e.g. `/root/results/<id>/...`) and a run can fail even if the controller math is correct.

## Goal

For every command input, run:

`parse flight plan → plan trajectory → simulate closed-loop → compute metrics → save artifacts → save plots`

Then verify completeness on disk before exiting.

## Runnable skeleton (Python)

```python
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np


def run_one_command(command_text: str, params: dict, out_dir: Path) -> dict:
    """Run the end-to-end pipeline for one command input and write all artifacts.

    Returns a dict of metadata (e.g., chosen gains, headline metrics).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    plots_dir = out_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    # --- Parse → plan ---
    waypoints, waypoint_times, modes = parse_flight_plan(command_text)
    planned = trajectory_planner(
        waypoints=waypoints,
        max_iter=params["max_iter"],
        waypoint_times=waypoint_times,
        sample_rate=params["sample_rate"],
        modes=modes,
    )
    np.save(out_dir / "planned_trajectory.npy", planned)

    # --- Simulate closed-loop (outer+inner+physics) ---
    # Expected to return actual_state (15, n) and desired_state (15, n) plus time.
    actual_state, desired_state, time_vec = simulate_closed_loop(planned, params)
    np.save(out_dir / "actual_trajectory.npy", actual_state)

    # --- Metrics + plots ---
    target = waypoints[0:3, -1]
    metrics = stepinfo_3d(actual_state[0:3, :], target, time_vec, settling_threshold=0.02)
    (out_dir / "metrics_3d.json").write_text(json.dumps(metrics, indent=2))

    plot_quadrotor(actual_state, desired_state, time_vec, save_dir=str(plots_dir))

    tuning_results = {
        "gains": params.get("gains", {}),
        "metrics": metrics,
    }
    (out_dir / "tuning_results.json").write_text(json.dumps(tuning_results, indent=2))

    return tuning_results


def completeness_check(results_root: Path, command_ids: list[str]) -> None:
    """Fail-fast if any required artifact is missing or unreadable."""
    required = [
        "planned_trajectory.npy",
        "actual_trajectory.npy",
        "metrics_3d.json",
        "tuning_results.json",
    ]

    for cmd_id in command_ids:
        out_dir = results_root / cmd_id
        assert out_dir.is_dir(), f"missing output dir: {out_dir}"

        for fname in required:
            path = out_dir / fname
            assert path.exists(), f"missing file: {path}"

        # Basic readability checks
        _ = np.load(out_dir / "planned_trajectory.npy")
        _ = np.load(out_dir / "actual_trajectory.npy")
        json.loads((out_dir / "metrics_3d.json").read_text())
        json.loads((out_dir / "tuning_results.json").read_text())

        plots_dir = out_dir / "plots"
        assert plots_dir.is_dir(), f"missing plots dir: {plots_dir}"


def main(command_texts: dict[str, str], params: dict) -> None:
    results_root = Path(params.get("results_root", "/root/results"))
    results_root.mkdir(parents=True, exist_ok=True)

    for cmd_id, text in command_texts.items():
        run_one_command(text, params=params, out_dir=results_root / cmd_id)

    completeness_check(results_root, command_ids=list(command_texts.keys()))


# --- Runtime branch: single-command debug mode vs full harness mode ---
if __name__ == "__main__":
    params = {
        "sample_rate": 200,
        "max_iter": 2000,
        "results_root": "/root/results",
        # optionally: "gains": {...}
    }

    debug_one = False
    if debug_one:
        main({"debug": "Take off to 1 m height in 3 seconds"}, params)
    else:
        # Replace with real enumeration of command inputs.
        main({"001": "...", "002": "..."}, params)
```

## Runtime branches (what to do)

- If you only need to validate controller math: set `debug_one=True`, run a single command, and still write artifacts (under `/root/results/debug/`) so you can inspect them.
- If you are running harness-facing evaluation: enumerate *all* command IDs/files, loop over all of them, and run `completeness_check` before exiting.

## Verification step (and corrective action)

1. Run the `completeness_check(...)`.
2. If it fails:
   - **Missing directory**: you did not create `/root/results/<id>/` (fix: create it before planning).
   - **Missing `planned_trajectory.npy`**: you did not save immediately after planning (fix: save right after planner returns).
   - **Missing `actual_trajectory.npy`**: your simulation did not run or did not return the expected matrix (fix: instrument simulation and save right after it returns).
   - **JSON parse error**: you wrote non-JSON or wrong schema (fix: write `dict` via `json.dumps` and include metrics/gains keys).
   - **Missing plots dir**: you did not call plotting with the per-command `plots/` directory (fix: `plot_quadrotor(..., save_dir=str(out_dir/'plots'))`).

After fixes, rerun `completeness_check` until it passes for every command ID.
