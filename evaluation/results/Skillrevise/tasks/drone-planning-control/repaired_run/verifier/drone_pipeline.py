import json
import math
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import yaml


@dataclass(frozen=True)
class CommandSpec:
    mode: str  # takeoff|hover|land|fly
    start_pos: np.ndarray  # (3,)
    end_pos: np.ndarray  # (3,)
    duration_s: float
    yaw: float = 0.0


def load_system_params(path: str = "system_params.yaml") -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        params = yaml.safe_load(f)
    params = dict(params)
    params["inertia"] = np.diag(np.array(params["inertia"], dtype=float))
    params["sample_rate"] = float(params["sample_rate"])
    return params


_takeoff_re = re.compile(
    r"^\s*Take\s+off\s+to\s*([0-9.]+)\s*m\s+height\s+in\s*([0-9.]+)\s*seconds\s*$",
    re.IGNORECASE,
)
_hover_re = re.compile(
    r"^\s*Hover\s+at\s*([0-9.]+)\s*m\s+height\s+for\s*([0-9.]+)\s*seconds\s*$",
    re.IGNORECASE,
)
_land_re = re.compile(
    r"^\s*Land\s+from\s*([0-9.]+)\s*m\s+height\s+in\s*([0-9.]+)\s*seconds\s*$",
    re.IGNORECASE,
)
_fly_re = re.compile(
    r"^\s*Fly\s+from\s*\(\s*([-0-9.]+)\s*,\s*([-0-9.]+)\s*,\s*([-0-9.]+)\s*\)\s*"
    r"to\s*\(\s*([-0-9.]+)\s*,\s*([-0-9.]+)\s*,\s*([-0-9.]+)\s*\)\s*"
    r"in\s*([0-9.]+)\s*seconds\s*$",
    re.IGNORECASE,
)


def parse_command_text(text: str) -> CommandSpec:
    line = text.strip()
    if m := _takeoff_re.match(line):
        h = float(m.group(1))
        t = float(m.group(2))
        return CommandSpec("takeoff", np.array([0.0, 0.0, 0.0]), np.array([0.0, 0.0, h]), t)

    if m := _hover_re.match(line):
        h = float(m.group(1))
        t = float(m.group(2))
        return CommandSpec("hover", np.array([0.0, 0.0, h]), np.array([0.0, 0.0, h]), t)

    if m := _land_re.match(line):
        h = float(m.group(1))
        t = float(m.group(2))
        return CommandSpec("land", np.array([0.0, 0.0, h]), np.array([0.0, 0.0, 0.0]), t)

    if m := _fly_re.match(line):
        x0, y0, z0 = float(m.group(1)), float(m.group(2)), float(m.group(3))
        x1, y1, z1 = float(m.group(4)), float(m.group(5)), float(m.group(6))
        t = float(m.group(7))
        return CommandSpec(
            "fly",
            np.array([x0, y0, z0], dtype=float),
            np.array([x1, y1, z1], dtype=float),
            t,
        )

    raise ValueError(f"Unsupported command line: {line!r}")


def min_jerk(p0: np.ndarray, pf: np.ndarray, t: np.ndarray, T: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    s = np.clip(t / T, 0.0, 1.0)
    s2 = s * s
    s3 = s2 * s
    s4 = s3 * s
    s5 = s4 * s

    h = 10.0 * s3 - 15.0 * s4 + 6.0 * s5
    hd = (30.0 * s2 - 60.0 * s3 + 30.0 * s4) / T
    hdd = (60.0 * s - 180.0 * s2 + 120.0 * s3) / (T * T)

    dp = (pf - p0).reshape(3, 1)
    pos = p0.reshape(3, 1) + dp * h.reshape(1, -1)
    vel = dp * hd.reshape(1, -1)
    acc = dp * hdd.reshape(1, -1)
    return pos, vel, acc


def enforce_accel_limits(acc: np.ndarray, params: Dict) -> None:
    ax, ay, az = acc
    horiz = np.sqrt(ax * ax + ay * ay)

    if np.any(az > params["accel_limit_up"] + 1e-9):
        raise ValueError("Planned az exceeds accel_limit_up")
    if np.any(az < -params["accel_limit_down"] - 1e-9):
        raise ValueError("Planned az exceeds accel_limit_down")
    if np.any(horiz > params["accel_limit_horiz"] + 1e-9):
        raise ValueError("Planned horizontal acceleration exceeds accel_limit_horiz")


def attitude_planner_from_accel(acc_xy: np.ndarray, yaw: float, g: float) -> np.ndarray:
    ax, ay = float(acc_xy[0]), float(acc_xy[1])
    phi = (ax * math.sin(yaw) - ay * math.cos(yaw)) / g
    theta = (ax * math.cos(yaw) + ay * math.sin(yaw)) / g
    return np.array([phi, theta, yaw], dtype=float)


def euler_to_R(phi: float, theta: float, psi: float) -> np.ndarray:
    cphi, sphi = math.cos(phi), math.sin(phi)
    cth, sth = math.cos(theta), math.sin(theta)
    cpsi, spsi = math.cos(psi), math.sin(psi)

    Rz = np.array([[cpsi, -spsi, 0.0], [spsi, cpsi, 0.0], [0.0, 0.0, 1.0]])
    Ry = np.array([[cth, 0.0, sth], [0.0, 1.0, 0.0], [-sth, 0.0, cth]])
    Rx = np.array([[1.0, 0.0, 0.0], [0.0, cphi, -sphi], [0.0, sphi, cphi]])
    return Rz @ Ry @ Rx


def euler_rate_matrix(phi: float, theta: float) -> np.ndarray:
    cth = math.cos(theta)
    sth = math.sin(theta)
    cphi = math.cos(phi)
    sphi = math.sin(phi)

    if abs(cth) < 1e-6:
        cth = 1e-6 if cth >= 0 else -1e-6

    return np.array(
        [
            [1.0, sphi * sth / cth, cphi * sth / cth],
            [0.0, cphi, -sphi],
            [0.0, sphi / cth, cphi / cth],
        ],
        dtype=float,
    )


def clamp_accel(a_cmd: np.ndarray, params: Dict) -> np.ndarray:
    a = a_cmd.copy()

    if a[2] > params["accel_limit_up"]:
        a[2] = params["accel_limit_up"]
    if a[2] < -params["accel_limit_down"]:
        a[2] = -params["accel_limit_down"]

    horiz = float(np.linalg.norm(a[:2]))
    lim = float(params["accel_limit_horiz"])
    if horiz > lim and horiz > 1e-12:
        a[:2] *= lim / horiz

    return a


def make_pos_integral() -> Dict[str, np.ndarray]:
    return {"e": np.zeros(3, dtype=float)}


def make_att_integral() -> Dict[str, np.ndarray]:
    return {"e": np.zeros(3, dtype=float)}


def position_controller(
    pos: np.ndarray,
    vel: np.ndarray,
    pos_des: np.ndarray,
    vel_des: np.ndarray,
    acc_des: np.ndarray,
    dt: float,
    gains: Dict[str, np.ndarray],
    integral: Dict[str, np.ndarray],
    params: Dict,
) -> np.ndarray:
    e_p = pos_des - pos
    e_v = vel_des - vel
    integral["e"] = integral["e"] + e_p * dt

    a_cmd = (
        acc_des
        + gains["kp_pos"] * e_p
        + gains["kd_pos"] * e_v
        + gains["ki_pos"] * integral["e"]
    )
    return clamp_accel(a_cmd, params)


def attitude_controller(
    rot: np.ndarray,
    omega: np.ndarray,
    rot_des: np.ndarray,
    omega_des: np.ndarray,
    dt: float,
    gains: Dict[str, np.ndarray],
    integral: Dict[str, np.ndarray],
    params: Dict,
) -> np.ndarray:
    e = rot_des - rot
    integral["e"] = integral["e"] + e * dt

    I = params["inertia"]
    u = gains["kp_att"] * e + gains["kd_att"] * (omega_des - omega) + gains["ki_att"] * integral["e"]
    return I @ u


class QuadModel:
    def __init__(self, params: Dict):
        self.params = params

        L = float(params["arm_length"])
        a = float(params["motor_spread_angle"])
        c, s = math.cos(a), math.sin(a)
        self.motor_xy = np.array(
            [[L * c, L * s], [-L * c, L * s], [-L * c, -L * s], [L * c, -L * s]],
            dtype=float,
        )
        self.yaw_dir = np.array([1.0, -1.0, 1.0, -1.0], dtype=float)

        self.kf = float(params["thrust_coefficient"])
        self.km = float(params["moment_scale"])
        self.kappa = self.km / self.kf

        self.rpm_min = float(params["rpm_min"])
        self.rpm_max = float(params["rpm_max"])
        self.f_min = self.kf * self.rpm_min * self.rpm_min
        self.f_max = self.kf * self.rpm_max * self.rpm_max

        self.alloc = self._build_allocation_matrix()
        self.alloc_inv = np.linalg.inv(self.alloc)

    def _build_allocation_matrix(self) -> np.ndarray:
        x = self.motor_xy[:, 0]
        y = self.motor_xy[:, 1]
        A = np.zeros((4, 4), dtype=float)
        A[0, :] = 1.0
        A[1, :] = y
        A[2, :] = -x
        A[3, :] = self.kappa * self.yaw_dir
        return A

    def mix_to_forces(self, T: float, M: np.ndarray) -> np.ndarray:
        u = np.array([T, float(M[0]), float(M[1]), float(M[2])], dtype=float)
        f = self.alloc_inv @ u
        return np.clip(f, self.f_min, self.f_max)

    def forces_to_rpm(self, f: np.ndarray) -> np.ndarray:
        return np.sqrt(np.maximum(f / self.kf, 0.0))

    def rpm_to_forces_moments(self, rpm: np.ndarray) -> Tuple[float, np.ndarray]:
        f = self.kf * rpm * rpm
        T = float(np.sum(f))
        x = self.motor_xy[:, 0]
        y = self.motor_xy[:, 1]
        Mx = float(np.sum(y * f))
        My = float(np.sum(-x * f))
        Mz = float(np.sum(self.yaw_dir * self.kappa * f))
        return T, np.array([Mx, My, Mz], dtype=float)


def simulate_command(
    cmd: CommandSpec,
    planned: np.ndarray,
    time_vec: np.ndarray,
    gains: Dict[str, np.ndarray],
    params: Dict,
) -> np.ndarray:
    dt = 1.0 / float(params["sample_rate"])
    m = float(params["mass"])
    g = float(params["gravity"])

    model = QuadModel(params)

    n = planned.shape[1]
    state = np.zeros((15, n), dtype=float)
    state[0:3, 0] = cmd.start_pos

    rpm = np.ones(4, dtype=float) * float(params["rpm_min"])

    pos_int = make_pos_integral()
    att_int = make_att_integral()

    for k in range(n - 1):
        pos = state[0:3, k]
        vel = state[3:6, k]
        rot = state[6:9, k]
        omega = state[9:12, k]

        pos_des = planned[0:3, k]
        vel_des = planned[3:6, k]
        acc_des = planned[12:15, k]

        a_cmd = position_controller(pos, vel, pos_des, vel_des, acc_des, dt, gains, pos_int, params)
        rot_des = attitude_planner_from_accel(a_cmd[:2], cmd.yaw, g)
        omega_des = np.zeros(3, dtype=float)

        phi_d, th_d = float(rot_des[0]), float(rot_des[1])
        denom = max(math.cos(phi_d) * math.cos(th_d), 0.2)
        T_cmd = m * (g + float(a_cmd[2])) / denom

        M_cmd = attitude_controller(rot, omega, rot_des, omega_des, dt, gains, att_int, params)

        f_cmd = model.mix_to_forces(T_cmd, M_cmd)
        rpm_cmd = model.forces_to_rpm(f_cmd)

        motor_k = float(params["motor_constant"])
        rpm = rpm + dt * motor_k * (rpm_cmd - rpm)
        rpm = np.clip(rpm, model.rpm_min, model.rpm_max)

        T, M = model.rpm_to_forces_moments(rpm)

        phi, theta, psi = float(rot[0]), float(rot[1]), float(rot[2])
        R = euler_to_R(phi, theta, psi)
        acc_world = (R @ np.array([0.0, 0.0, T], dtype=float)) / m - np.array([0.0, 0.0, g], dtype=float)

        I = params["inertia"]
        omega_dot = np.linalg.solve(I, M - np.cross(omega, I @ omega))

        E = euler_rate_matrix(phi, theta)
        euler_dot = E @ omega

        state[12:15, k] = acc_world

        state[0:3, k + 1] = pos + dt * vel
        state[3:6, k + 1] = vel + dt * acc_world
        state[6:9, k + 1] = rot + dt * euler_dot
        state[9:12, k + 1] = omega + dt * omega_dot

    state[12:15, -1] = state[12:15, -2]
    return state


def stepinfo_3d(pos_actual: np.ndarray, pos_target: np.ndarray, t: np.ndarray, settling_threshold: float = 0.02) -> Dict[str, float]:
    d = np.linalg.norm(pos_actual.T - pos_target.reshape(1, 3), axis=1)
    d0 = float(d[0])
    if d0 < 1e-6:
        return {"RiseTime": 0.0, "SettlingTime": 0.0, "Overshoot_pct": 0.0, "SteadyStateError": float(d[-1])}

    rise = 0.0
    for k in range(len(d)):
        if d[k] <= 0.1 * d0:
            rise = float(t[k])
            break

    band = settling_threshold * d0
    settle = float(t[-1])
    for k in range(len(d) - 1, -1, -1):
        if d[k] > band:
            settle = float(t[min(k + 1, len(t) - 1)])
            break

    entered_idx = None
    for k in range(len(d)):
        if d[k] <= band:
            entered_idx = k
            break
    overshoot = 0.0
    if entered_idx is not None:
        overshoot = float(np.max(d[entered_idx:]) / d0 * 100.0)

    return {
        "RiseTime": rise,
        "SettlingTime": settle,
        "Overshoot_pct": overshoot,
        "SteadyStateError": float(d[-1]),
    }


def plot_run(state: np.ndarray, state_des: np.ndarray, t: np.ndarray, save_dir: str, params: Dict) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(save_dir, exist_ok=True)

    time_step = 1.0 / float(params["sample_rate"])

    groups = [
        (slice(0, 3), ["x", "y", "z"], "pos"),
        (slice(3, 6), ["vx", "vy", "vz"], "vel"),
        (slice(6, 9), [r"$\phi$", r"$\theta$", r"$\psi$"], "rot"),
        (slice(9, 12), ["p", "q", "r"], "omega"),
        (slice(12, 15), ["ax", "ay", "az"], "acc"),
    ]

    def _grid_fig(title: str):
        fig, axes = plt.subplots(5, 3, figsize=(16, 20), sharex=True)
        fig.suptitle(title)
        return fig, axes

    fig1, axes1 = _grid_fig("Desired vs Actual")
    fig2, axes2 = _grid_fig("Errors (actual - desired)")
    fig3, axes3 = _grid_fig("Cumulative absolute errors")

    for gi, (sl, labels, _name) in enumerate(groups):
        act = state[sl, :]
        des = state_des[sl, :]
        err = act - des
        cum = time_step * np.cumsum(np.abs(err), axis=1)

        for j in range(3):
            ax = axes1[gi, j]
            ax.plot(t, des[j, :], "b", linewidth=1)
            ax.plot(t, act[j, :], "r", linewidth=1)
            ax.set_ylabel(labels[j])

            ax = axes2[gi, j]
            ax.plot(t, err[j, :], "k", linewidth=1)
            ax.set_ylabel(labels[j])

            ax = axes3[gi, j]
            ax.plot(t, cum[j, :], "k", linewidth=1)
            ax.set_ylabel(labels[j])

    for ax in axes1[-1, :]:
        ax.set_xlabel("t [s]")
    for ax in axes2[-1, :]:
        ax.set_xlabel("t [s]")
    for ax in axes3[-1, :]:
        ax.set_xlabel("t [s]")

    fig1.tight_layout()
    fig2.tight_layout()
    fig3.tight_layout()

    fig1.savefig(os.path.join(save_dir, "desired_vs_actual.png"))
    fig2.savefig(os.path.join(save_dir, "errors.png"))
    fig3.savefig(os.path.join(save_dir, "cumulative_errors.png"))

    plt.close(fig1)
    plt.close(fig2)
    plt.close(fig3)


def generate_planned_trajectory(cmd: CommandSpec, params: Dict) -> Tuple[np.ndarray, np.ndarray]:
    sr = float(params["sample_rate"])
    dt = 1.0 / sr
    n = int(round(cmd.duration_s * sr)) + 1
    t = np.arange(n, dtype=float) * dt

    state_des = np.zeros((15, n), dtype=float)

    if cmd.mode == "hover":
        state_des[0:3, :] = cmd.end_pos.reshape(3, 1)
        return state_des, t

    pos, vel, acc = min_jerk(cmd.start_pos, cmd.end_pos, t, cmd.duration_s)
    enforce_accel_limits(acc, params)

    state_des[0:3, :] = pos
    state_des[3:6, :] = vel
    state_des[12:15, :] = acc

    g = float(params["gravity"])
    for k in range(n):
        rot = attitude_planner_from_accel(acc[0:2, k], cmd.yaw, g)
        state_des[6:9, k] = rot

    return state_des, t


def score_run(actual: np.ndarray, planned: np.ndarray, cmd: CommandSpec, t: np.ndarray) -> Dict[str, float]:
    err = np.linalg.norm((actual[0:3, :] - planned[0:3, :]).T, axis=1)
    max_err = float(np.max(err))

    metrics = stepinfo_3d(actual[0:3, :], cmd.end_pos, t, settling_threshold=0.02)
    metrics["mode"] = cmd.mode

    return {
        "max_pos_err": max_err,
        "RiseTime": float(metrics["RiseTime"]),
        "SettlingTime": float(metrics["SettlingTime"]),
        "Overshoot_pct": float(metrics["Overshoot_pct"]),
        "SteadyStateError": float(metrics["SteadyStateError"]),
    }


def tune_gains_for_command(cmd: CommandSpec, planned: np.ndarray, t: np.ndarray, params: Dict) -> Tuple[Dict[str, np.ndarray], np.ndarray, Dict[str, float]]:
    if cmd.mode in {"takeoff", "land"}:
        base = {
            "kp_pos": np.array([7.0, 7.0, 14.0]),
            "kd_pos": np.array([5.0, 5.0, 10.0]),
            "ki_pos": np.array([0.05, 0.05, 0.10]),
        }
    elif cmd.mode == "fly":
        base = {
            "kp_pos": np.array([12.0, 12.0, 14.0]),
            "kd_pos": np.array([7.0, 7.0, 10.0]),
            "ki_pos": np.array([0.03, 0.03, 0.08]),
        }
    else:  # hover
        base = {
            "kp_pos": np.array([7.0, 7.0, 12.0]),
            "kd_pos": np.array([5.0, 5.0, 9.0]),
            "ki_pos": np.array([0.02, 0.02, 0.05]),
        }

    base_att = {
        "kp_att": np.array([200.0, 200.0, 120.0]),
        "kd_att": np.array([25.0, 25.0, 12.0]),
        "ki_att": np.array([0.0, 0.0, 0.0]),
    }

    pos_scales = [0.7, 0.9, 1.0, 1.2, 1.5, 2.0]
    att_scales = [0.8, 1.0, 1.2]

    best = None
    best_actual = None
    best_score = None

    def is_success(s: Dict[str, float]) -> bool:
        return (
            s["SteadyStateError"] < 0.05
            and s["Overshoot_pct"] < 5.0
            and s["max_pos_err"] < 0.05
        )

    for ps in pos_scales:
        for ats in att_scales:
            gains = {
                **{k: v * ps for k, v in base.items()},
                **{k: v * ats for k, v in base_att.items()},
            }

            actual = simulate_command(cmd, planned, t, gains, params)
            if not np.isfinite(actual).all():
                continue

            s = score_run(actual, planned, cmd, t)

            cand = (0 if is_success(s) else 1, s["max_pos_err"], s["SteadyStateError"], s["Overshoot_pct"], s["SettlingTime"])
            if best is None or cand < best:
                best = cand
                best_actual = actual
                best_score = s
                best_gains = gains

    assert best_actual is not None and best_score is not None
    return best_gains, best_actual, best_score


def write_json(path: str, obj: Dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=False)


def gains_to_json(gains: Dict[str, np.ndarray]) -> Dict:
    return {
        "kp_pos": [float(x) for x in gains["kp_pos"]],
        "ki_pos": [float(x) for x in gains["ki_pos"]],
        "kd_pos": [float(x) for x in gains["kd_pos"]],
        "kp_att": [float(x) for x in gains["kp_att"]],
        "ki_att": [float(x) for x in gains["ki_att"]],
        "kd_att": [float(x) for x in gains["kd_att"]],
    }


def generate_results_for_file(cmd_path: str, out_dir: str, params: Dict) -> Dict[str, float]:
    with open(cmd_path, "r", encoding="utf-8") as f:
        cmd_text = f.read()
    cmd = parse_command_text(cmd_text)

    planned, t = generate_planned_trajectory(cmd, params)
    gains, actual, score = tune_gains_for_command(cmd, planned, t, params)

    os.makedirs(out_dir, exist_ok=True)

    metrics = stepinfo_3d(actual[0:3, :], cmd.end_pos, t, settling_threshold=0.02)
    metrics_obj = {
        "mode": cmd.mode,
        "RiseTime": float(metrics["RiseTime"]),
        "SettlingTime": float(metrics["SettlingTime"]),
        "Overshoot_pct": float(metrics["Overshoot_pct"]),
        "SteadyStateError": float(metrics["SteadyStateError"]),
    }

    write_json(os.path.join(out_dir, "metrics_3d.json"), metrics_obj)
    write_json(os.path.join(out_dir, "tuning_results.json"), gains_to_json(gains))

    np.save(os.path.join(out_dir, "planned_trajectory.npy"), planned)
    np.save(os.path.join(out_dir, "actual_trajectory.npy"), actual)

    plot_run(actual, planned, t, os.path.join(out_dir, "plots"), params)

    return score


def main() -> None:
    params = load_system_params("system_params.yaml")

    commands_dir = "commands"
    results_root = "/root/results"
    os.makedirs(results_root, exist_ok=True)

    cmd_files = sorted(
        [f for f in os.listdir(commands_dir) if re.fullmatch(r"\d{3}\.txt", f)],
    )

    summary = {}
    for fname in cmd_files:
        cmd_path = os.path.join(commands_dir, fname)
        run_id = os.path.splitext(fname)[0]
        out_dir = os.path.join(results_root, run_id)
        score = generate_results_for_file(cmd_path, out_dir, params)
        summary[run_id] = score

    write_json(os.path.join(results_root, "summary.json"), summary)


if __name__ == "__main__":
    main()
