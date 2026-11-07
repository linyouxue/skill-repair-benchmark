"""Orchestrator: parse → plan → simulate → verify → emit artifacts."""
import os
import sys
import json
import glob
import yaml
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.flight_plan_parser import parse_flight_plan
from src.trajectory_planner import plan_trajectory
from src.simulator import simulate
from src.stepinfo_3d import stepinfo_3d
from src.plotting import generate_plots


ROOT = "/root"
COMMANDS_DIR = os.path.join(ROOT, "commands")
RESULTS_DIR = os.path.join(ROOT, "results")
PARAMS_PATH = os.path.join(ROOT, "system_params.yaml")


DEFAULT_GAINS = {
    "kp_pos": [10.0, 10.0, 10.0],
    "ki_pos": [0.5, 0.5, 2.0],
    "kd_pos": [6.5, 6.5, 6.5],
    "kp_att": [380.0, 380.0, 60.0],
    "ki_att": [0.0, 0.0, 0.0],
    "kd_att": [35.0, 35.0, 15.0],
}


def load_params():
    with open(PARAMS_PATH, "r") as f:
        return yaml.safe_load(f)


def mode_of(modes):
    """Pick the single mode descriptor for a command (we expect one segment)."""
    return modes[0] if modes else "unknown"


def verify_accel_limits(planned, params):
    """Check planned acceleration stays within physical limits."""
    acc = planned[12:15, :]
    ax, ay, az = acc[0], acc[1], acc[2]
    up_ok = np.all(az <= params["accel_limit_up"] + 1e-6)
    down_ok = np.all(az >= -params["accel_limit_down"] - 1e-6)
    horiz = np.sqrt(ax ** 2 + ay ** 2)
    horiz_ok = np.all(horiz <= params["accel_limit_horiz"] + 1e-6)
    return bool(up_ok and down_ok and horiz_ok), {
        "az_max": float(np.max(az)),
        "az_min": float(np.min(az)),
        "horiz_max": float(np.max(horiz)),
    }


def run_one(cmd_path, params):
    cmd_name = os.path.splitext(os.path.basename(cmd_path))[0]
    with open(cmd_path, "r") as f:
        text = f.read()

    waypoints, waypoint_times, modes = parse_flight_plan(text)
    planned, t_vec = plan_trajectory(waypoints, waypoint_times, modes,
                                     params["sample_rate"])
    N = planned.shape[1]

    # Verify planned acceleration limits
    accel_ok, accel_info = verify_accel_limits(planned, params)
    if not accel_ok:
        raise RuntimeError(f"[{cmd_name}] planned trajectory violates accel limits: {accel_info}")

    gains = {k: list(v) for k, v in DEFAULT_GAINS.items()}

    actual = simulate(planned, t_vec, params, gains)

    # Per-timestep position error
    perr = np.linalg.norm(actual[0:3, :] - planned[0:3, :], axis=0)
    max_err = float(np.max(perr))

    # Metrics
    pos_target = planned[0:3, -1]
    metrics = stepinfo_3d(actual[0:3, :], pos_target, t_vec, settling_threshold=0.02)
    metrics_out = {"mode": mode_of(modes), **metrics}

    # Save artifacts
    out_dir = os.path.join(RESULTS_DIR, cmd_name)
    os.makedirs(out_dir, exist_ok=True)
    np.save(os.path.join(out_dir, "planned_trajectory.npy"), planned)
    np.save(os.path.join(out_dir, "actual_trajectory.npy"), actual)
    with open(os.path.join(out_dir, "metrics_3d.json"), "w") as f:
        json.dump(metrics_out, f, indent=2)
    with open(os.path.join(out_dir, "tuning_results.json"), "w") as f:
        json.dump(gains, f, indent=2)

    plot_dir = os.path.join(out_dir, "plots")
    time_step = 1.0 / params["sample_rate"]
    generate_plots(actual, planned, t_vec, plot_dir, time_step)

    pass_err = max_err < 0.05
    pass_over = metrics["Overshoot_pct"] < 5.0
    pass_sse = metrics["SteadyStateError"] < 0.05
    status = "PASS" if (pass_err and pass_over and pass_sse and accel_ok) else "FAIL"

    print(f"[{cmd_name}] {status}  mode={mode_of(modes):>8}  "
          f"max_err={max_err:.4f} m  "
          f"SSE={metrics['SteadyStateError']:.4f} m  "
          f"Over={metrics['Overshoot_pct']:.2f}%  "
          f"Rise={metrics['RiseTime']:.3f}s  "
          f"Settle={metrics['SettlingTime']:.3f}s  "
          f"accel(z∈[{accel_info['az_min']:.2f},{accel_info['az_max']:.2f}], horiz≤{accel_info['horiz_max']:.2f})")

    return {
        "cmd": cmd_name,
        "mode": mode_of(modes),
        "max_err": max_err,
        "metrics": metrics,
        "status": status,
    }


def main():
    params = load_params()
    cmd_files = sorted(glob.glob(os.path.join(COMMANDS_DIR, "*.txt")))

    only = sys.argv[1:] if len(sys.argv) > 1 else None
    if only:
        cmd_files = [f for f in cmd_files
                     if os.path.splitext(os.path.basename(f))[0] in only]

    results = []
    for f in cmd_files:
        try:
            r = run_one(f, params)
            results.append(r)
        except Exception as e:
            print(f"[{os.path.basename(f)}] ERROR: {e}")
            raise

    passed = sum(1 for r in results if r["status"] == "PASS")
    print(f"\n{passed}/{len(results)} passed")


if __name__ == "__main__":
    main()
