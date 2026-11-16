from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from drone_sim.command_parser import parse_command_text
from drone_sim.metrics import stepinfo_3d
from drone_sim.params import load_system_params
from drone_sim.plotting import plot_quadrotor
from drone_sim.trajectory import plan_trajectory
from drone_sim.tuning import tune_pid


def _gains_to_json(g):
    return [float(g[0]), float(g[1]), float(g[2])]


def main() -> None:
    params = load_system_params("/root/system_params.yaml")

    commands_dir = Path("/root/commands")
    out_root = Path("/root/results")
    out_root.mkdir(parents=True, exist_ok=True)

    cmd_files = sorted(commands_dir.glob("*.txt"))
    if not cmd_files:
        raise RuntimeError("No command files found under /root/commands")

    for path in cmd_files:
        cmd_id = path.stem
        text = path.read_text().strip()
        cmd = parse_command_text(text)

        state_des, t = plan_trajectory(cmd, params)

        # Per-command deterministic seed.
        seed = int(cmd_id)
        tuning = tune_pid(cmd, state_des, t, params, seed=seed)

        state_act = tuning.state_actual

        # Metrics (requested schema includes mode field)
        m = stepinfo_3d(state_act[0:3, :], state_des[0:3, -1], t, settling_threshold=0.02)
        metrics_out = {
            "mode": cmd.mode,
            "RiseTime": float(m["RiseTime"]),
            "SettlingTime": float(m["SettlingTime"]),
            "Overshoot_pct": float(m["Overshoot_pct"]),
            "SteadyStateError": float(m["SteadyStateError"]),
        }

        # Output folder
        out_dir = out_root / cmd_id
        plots_dir = out_dir / "plots"
        plots_dir.mkdir(parents=True, exist_ok=True)

        np.save(str(out_dir / "planned_trajectory.npy"), state_des)
        np.save(str(out_dir / "actual_trajectory.npy"), state_act)

        tuning_out = {
            "kp_pos": _gains_to_json(tuning.gains_pos.kp),
            "ki_pos": _gains_to_json(tuning.gains_pos.ki),
            "kd_pos": _gains_to_json(tuning.gains_pos.kd),
            "kp_att": _gains_to_json(tuning.gains_att.kp),
            "ki_att": _gains_to_json(tuning.gains_att.ki),
            "kd_att": _gains_to_json(tuning.gains_att.kd),
        }

        (out_dir / "metrics_3d.json").write_text(json.dumps(metrics_out, indent=2))
        (out_dir / "tuning_results.json").write_text(json.dumps(tuning_out, indent=2))

        plot_quadrotor(state_act, state_des, t, str(plots_dir))

        # Print a compact compliance summary.
        err = np.linalg.norm((state_act[0:3, :] - state_des[0:3, :]).T, axis=1)
        max_err = float(np.max(err))
        print(
            f"{cmd_id} {cmd.mode:7s} max_err={max_err:.4f} sse={metrics_out['SteadyStateError']:.4f} "
            f"OS={metrics_out['Overshoot_pct']:.2f}% settle={metrics_out['SettlingTime']:.2f}s"
        )


if __name__ == "__main__":
    main()
