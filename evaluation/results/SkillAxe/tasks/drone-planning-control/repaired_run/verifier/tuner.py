import copy

import numpy as np

from simulate import simulate_trajectory
from stepinfo_3d import stepinfo_3d


def _scale(arr: list[float], s: float) -> list[float]:
    return [float(x) * float(s) for x in arr]


def default_gains() -> dict:
    return {
        "kp_pos": [6.0, 6.0, 10.0],
        "ki_pos": [0.0, 0.0, 0.0],
        "kd_pos": [4.5, 4.5, 7.0],
        "kp_att": [250.0, 250.0, 150.0],
        "ki_att": [0.0, 0.0, 0.0],
        "kd_att": [30.0, 30.0, 20.0],
    }


def candidate_gains() -> list[dict]:
    base = default_gains()
    cands: list[dict] = []

    def add(mod: dict) -> None:
        g = copy.deepcopy(base)
        for k, v in mod.items():
            g[k] = v
        cands.append(g)

    add({})
    add({"kp_pos": _scale(base["kp_pos"], 1.2)})
    add({"kd_pos": _scale(base["kd_pos"], 1.2)})
    add({"kp_pos": _scale(base["kp_pos"], 1.4), "kd_pos": _scale(base["kd_pos"], 1.2)})
    add({"kp_pos": _scale(base["kp_pos"], 0.8), "kd_pos": _scale(base["kd_pos"], 0.8)})
    add({"kp_att": _scale(base["kp_att"], 1.2)})
    add({"kd_att": _scale(base["kd_att"], 1.2)})
    add({
        "kp_pos": _scale(base["kp_pos"], 1.2),
        "kd_pos": _scale(base["kd_pos"], 1.2),
        "kp_att": _scale(base["kp_att"], 1.2),
        "kd_att": _scale(base["kd_att"], 1.2),
    })
    add({
        "kp_pos": _scale(base["kp_pos"], 0.9),
        "kd_pos": _scale(base["kd_pos"], 0.9),
        "kp_att": _scale(base["kp_att"], 0.9),
        "kd_att": _scale(base["kd_att"], 0.9),
    })

    return cands


def tune_pid_for_command(desired: np.ndarray, params: dict) -> tuple[dict, dict]:
    desired = np.asarray(desired, dtype=float)
    dt = float(params["dt"])
    t = np.arange(desired.shape[1], dtype=float) * dt
    target = desired[0:3, -1]

    best = None
    best_score = None
    best_eval = None

    for gains in candidate_gains():
        actual, _, sim_summary = simulate_trajectory(desired, params, gains)

        metrics = stepinfo_3d(actual[0:3, :], target, t, settling_threshold=0.02)
        max_err = sim_summary["max_pos_error"]

        ok = (
            max_err < 0.05
            and metrics["SteadyStateError"] < 0.05
            and metrics["Overshoot_pct"] < 5.0
        )

        score = float(max_err)
        if not ok:
            score += 1.0
            score += 5.0 * max(0.0, metrics["SteadyStateError"] - 0.05)
            score += 0.2 * max(0.0, metrics["Overshoot_pct"] - 5.0)

        if best_score is None or score < best_score:
            best_score = score
            best = gains
            best_eval = {"score": score, "ok": ok, **sim_summary, **metrics}

    assert best is not None and best_eval is not None
    return best, best_eval
