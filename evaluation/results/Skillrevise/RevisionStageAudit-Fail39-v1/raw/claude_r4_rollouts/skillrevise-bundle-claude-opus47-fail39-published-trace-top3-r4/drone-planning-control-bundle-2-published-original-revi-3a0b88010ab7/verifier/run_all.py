"""Orchestrator: run every command, write artifacts, verify acceptance criteria."""
import json
import os
import sys
import glob
import numpy as np

from drone_sim import (
    load_params, parse_flight_plan, plan_trajectory, simulate, stepinfo_3d,
)
from plot_quadrotor import generate_plots


RESULTS_ROOT = "/root/results"
COMMANDS_DIR = "/root/commands"


# Attitude inner loop gains constrained by motor time constant (km=36.5 → τ≈27ms).
# For stability the attitude closed-loop ω_n must stay well below km. Target ω_n ≈ 8 rad/s
# with heavy damping; empirically kp≈1-2, kd≈0.3 gives sub-mm tracking.
DEFAULT_GAINS = {
    "kp_pos": [6.0,  6.0,  10.0],
    "ki_pos": [0.3,  0.3,  2.0],
    "kd_pos": [4.5,  4.5,  6.5],
    "kp_att": [1.5,  1.5,  2.0],
    "ki_att": [0.0,  0.0,  0.0],
    "kd_att": [0.3,  0.3,  0.4],
}


def gains_for(mode):
    g = {k: list(v) for k, v in DEFAULT_GAINS.items()}
    if mode == "takeoff":
        g["kp_pos"] = [6.0, 6.0, 12.0]
        g["kd_pos"] = [4.5, 4.5, 7.0]
        g["ki_pos"] = [0.3, 0.3, 2.0]
    elif mode == "hover":
        g["kp_pos"] = [6.0, 6.0, 12.0]
        g["kd_pos"] = [4.5, 4.5, 7.0]
        g["ki_pos"] = [0.3, 0.3, 2.5]
    elif mode == "land":
        g["kp_pos"] = [6.0, 6.0, 12.0]
        g["kd_pos"] = [4.5, 4.5, 7.0]
        g["ki_pos"] = [0.3, 0.3, 2.0]
    elif mode == "fly":
        g["kp_pos"] = [6.0, 6.0, 12.0]
        g["kd_pos"] = [4.5, 4.5, 7.0]
        g["ki_pos"] = [0.3, 0.3, 2.0]
    return g


def verify_accel_limits(planned, params):
    ax = planned[12]
    ay = planned[13]
    az = planned[14]
    horiz = np.sqrt(ax * ax + ay * ay)
    assert horiz.max() <= params["accel_limit_horiz"] + 1e-6, \
        f"Planned horiz accel {horiz.max():.3f} > limit {params['accel_limit_horiz']}"
    assert az.max() <= params["accel_limit_up"] + 1e-6, \
        f"Planned up accel {az.max():.3f} > limit {params['accel_limit_up']}"
    assert az.min() >= -params["accel_limit_down"] - 1e-6, \
        f"Planned down accel {az.min():.3f} < -limit {-params['accel_limit_down']}"


def run_one(cmd_path, params):
    name = os.path.splitext(os.path.basename(cmd_path))[0]
    out_dir = os.path.join(RESULTS_ROOT, name)
    plots_dir = os.path.join(out_dir, "plots")
    os.makedirs(plots_dir, exist_ok=True)

    with open(cmd_path) as f:
        text = f.read()
    waypoints, times, modes = parse_flight_plan(text)
    assert len(modes) == 1, f"{name}: expected single-command file, got {modes}"
    mode = modes[0]
    start_pos = waypoints[0:3, 0].copy()

    dt = params["dt"]
    planned, t_vec = plan_trajectory(waypoints, times, modes, dt)
    verify_accel_limits(planned, params)

    gains = gains_for(mode)
    actual = simulate(params, planned, gains, start_pos)

    # Per-timestep tracking check
    err = np.linalg.norm(actual[0:3] - planned[0:3], axis=0)
    max_err = float(err.max())

    pos_target = waypoints[0:3, -1]
    metrics = stepinfo_3d(actual[0:3], pos_target, t_vec, settling_threshold=0.02)
    metrics["mode"] = mode
    metrics_out = {
        "mode":              mode,
        "RiseTime":          metrics["RiseTime"],
        "SettlingTime":      metrics["SettlingTime"],
        "Overshoot_pct":     metrics["Overshoot_pct"],
        "SteadyStateError":  metrics["SteadyStateError"],
    }

    np.save(os.path.join(out_dir, "planned_trajectory.npy"), planned)
    np.save(os.path.join(out_dir, "actual_trajectory.npy"), actual)
    with open(os.path.join(out_dir, "metrics_3d.json"), "w") as f:
        json.dump(metrics_out, f, indent=2)
    with open(os.path.join(out_dir, "tuning_results.json"), "w") as f:
        json.dump(gains, f, indent=2)
    generate_plots(actual, planned, t_vec, plots_dir, params["sample_rate"])

    # Acceptance checks
    ok_track = max_err < 0.05
    ok_sse   = metrics_out["SteadyStateError"] < 0.05
    ok_os    = metrics_out["Overshoot_pct"] < 5.0
    status = "PASS" if (ok_track and ok_sse and ok_os) else "FAIL"
    print(f"[{status}] {name:>3s} mode={mode:7s} max_err={max_err:.4f}m "
          f"SSE={metrics_out['SteadyStateError']:.4f} "
          f"OS={metrics_out['Overshoot_pct']:.3f}% "
          f"RT={metrics_out['RiseTime']:.3f} ST={metrics_out['SettlingTime']:.3f}")
    return status, max_err, metrics_out


def main(filter_names=None):
    params = load_params()
    cmds = sorted(glob.glob(os.path.join(COMMANDS_DIR, "*.txt")))
    if filter_names:
        cmds = [c for c in cmds if os.path.splitext(os.path.basename(c))[0] in filter_names]
    fails = []
    for cmd in cmds:
        status, _, _ = run_one(cmd, params)
        if status != "PASS":
            fails.append(os.path.basename(cmd))
    print("---")
    print(f"Total: {len(cmds)}  Fails: {len(fails)}")
    if fails:
        print("Failed:", fails)
    return fails


if __name__ == "__main__":
    arg = sys.argv[1:] if len(sys.argv) > 1 else None
    main(arg)
