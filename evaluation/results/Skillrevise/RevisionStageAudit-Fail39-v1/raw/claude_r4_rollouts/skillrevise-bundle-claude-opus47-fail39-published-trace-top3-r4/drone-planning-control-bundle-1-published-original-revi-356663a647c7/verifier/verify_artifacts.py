"""Independent artifact verifier: reload every file and re-check thresholds."""
import os
import json
import glob
import numpy as np
import yaml

ROOT = "/root"
RESULTS = os.path.join(ROOT, "results")
PARAMS = yaml.safe_load(open(os.path.join(ROOT, "system_params.yaml")))

req_json = {"metrics_3d.json", "tuning_results.json"}
req_npy = {"planned_trajectory.npy", "actual_trajectory.npy"}
req_plots = {"desired_vs_actual.png", "errors.png", "cumulative_errors.png"}

tune_keys = {"kp_pos", "ki_pos", "kd_pos", "kp_att", "ki_att", "kd_att"}
met_keys = {"mode", "RiseTime", "SettlingTime", "Overshoot_pct", "SteadyStateError"}

dirs = sorted(glob.glob(os.path.join(RESULTS, "*")))
failures = 0
for d in dirs:
    name = os.path.basename(d)
    probs = []
    files = set(os.listdir(d))
    for f in req_json | req_npy:
        if f not in files:
            probs.append(f"missing {f}")
    plot_dir = os.path.join(d, "plots")
    if not os.path.isdir(plot_dir):
        probs.append("missing plots/")
    else:
        pfiles = set(os.listdir(plot_dir))
        for f in req_plots:
            if f not in pfiles:
                probs.append(f"missing plots/{f}")

    met = json.load(open(os.path.join(d, "metrics_3d.json")))
    if set(met.keys()) != met_keys:
        probs.append(f"metrics keys {set(met.keys())}")
    tun = json.load(open(os.path.join(d, "tuning_results.json")))
    if set(tun.keys()) != tune_keys:
        probs.append(f"tuning keys {set(tun.keys())}")
    for k in tune_keys:
        if len(tun[k]) != 3:
            probs.append(f"tuning {k} not 3-vec")

    plan = np.load(os.path.join(d, "planned_trajectory.npy"))
    act = np.load(os.path.join(d, "actual_trajectory.npy"))
    if plan.shape[0] != 15 or act.shape[0] != 15:
        probs.append(f"shape rows plan={plan.shape} act={act.shape}")
    if plan.shape != act.shape:
        probs.append(f"planned {plan.shape} vs actual {act.shape}")

    # per-timestep position error < 0.05
    perr = np.linalg.norm(plan[0:3] - act[0:3], axis=0)
    if np.max(perr) >= 0.05:
        probs.append(f"max pos err {np.max(perr):.4f} ≥ 0.05")

    # acceleration limits
    acc = plan[12:15]
    if np.any(acc[2] > PARAMS["accel_limit_up"] + 1e-6):
        probs.append(f"az > up_limit (max {acc[2].max():.3f})")
    if np.any(acc[2] < -PARAMS["accel_limit_down"] - 1e-6):
        probs.append(f"az < -down_limit (min {acc[2].min():.3f})")
    horiz = np.sqrt(acc[0]**2 + acc[1]**2)
    if np.any(horiz > PARAMS["accel_limit_horiz"] + 1e-6):
        probs.append(f"horiz accel > limit (max {horiz.max():.3f})")

    # metric thresholds
    if met["Overshoot_pct"] >= 5.0:
        probs.append(f"overshoot {met['Overshoot_pct']:.2f}% ≥ 5")
    if met["SteadyStateError"] >= 0.05:
        probs.append(f"SSE {met['SteadyStateError']:.4f} ≥ 0.05")

    tag = "OK" if not probs else "FAIL"
    print(f"{name}: {tag}  perr_max={perr.max():.4f}  SSE={met['SteadyStateError']:.4f}  over={met['Overshoot_pct']:.2f}%")
    if probs:
        failures += 1
        for p in probs:
            print(f"   - {p}")

print(f"\n{len(dirs) - failures}/{len(dirs)} artifact sets fully valid")
