import json
import math
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import yaml


@dataclass(frozen=True)
class Params:
    sample_rate: float
    dt: float

    mass: float
    gravity: float

    arm_length: float
    thrust_coefficient: float
    moment_scale: float
    motor_constant: float
    rpm_min: float
    rpm_max: float
    inertia: np.ndarray

    accel_limit_up: float
    accel_limit_down: float
    accel_limit_horiz: float

    prop_matrix: np.ndarray
    prop_matrix_inv: np.ndarray

    thrust_min: float
    thrust_max: float
    moment_max: np.ndarray


def load_params(path: str) -> Params:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    sample_rate = float(raw["sample_rate"])
    dt = 1.0 / sample_rate

    mass = float(raw["mass"])
    gravity = float(raw["gravity"])

    arm_length = float(raw["arm_length"])
    cT = float(raw["thrust_coefficient"])
    cQ = float(raw["moment_scale"])

    km = float(raw["motor_constant"])
    rpm_min = float(raw["rpm_min"])
    rpm_max = float(raw["rpm_max"])

    inertia_diag = np.array(raw["inertia"], dtype=float)
    inertia = np.diag(inertia_diag)

    accel_limit_up = float(raw["accel_limit_up"])
    accel_limit_down = float(raw["accel_limit_down"])
    accel_limit_horiz = float(raw["accel_limit_horiz"])

    prop_matrix = np.array(
        [
            [cT, cT, cT, cT],
            [0.0, arm_length * cT, 0.0, -arm_length * cT],
            [-arm_length * cT, 0.0, arm_length * cT, 0.0],
            [-cQ, cQ, -cQ, cQ],
        ],
        dtype=float,
    )
    prop_matrix_inv = np.linalg.inv(prop_matrix)

    thrust_min = 4.0 * cT * (rpm_min**2)
    thrust_max = 4.0 * cT * (rpm_max**2)

    moment_max = np.array(
        [
            arm_length * cT * (rpm_max**2 - rpm_min**2),
            arm_length * cT * (rpm_max**2 - rpm_min**2),
            cQ * (rpm_max**2 - rpm_min**2),
        ],
        dtype=float,
    )

    return Params(
        sample_rate=sample_rate,
        dt=dt,
        mass=mass,
        gravity=gravity,
        arm_length=arm_length,
        thrust_coefficient=cT,
        moment_scale=cQ,
        motor_constant=km,
        rpm_min=rpm_min,
        rpm_max=rpm_max,
        inertia=inertia,
        accel_limit_up=accel_limit_up,
        accel_limit_down=accel_limit_down,
        accel_limit_horiz=accel_limit_horiz,
        prop_matrix=prop_matrix,
        prop_matrix_inv=prop_matrix_inv,
        thrust_min=thrust_min,
        thrust_max=thrust_max,
        moment_max=moment_max,
    )


def rot_matrix_zyx(phi: float, theta: float, psi: float) -> np.ndarray:
    cphi, sphi = math.cos(phi), math.sin(phi)
    cth, sth = math.cos(theta), math.sin(theta)
    cpsi, spsi = math.cos(psi), math.sin(psi)

    r00 = cpsi * cth
    r01 = cpsi * sth * sphi - spsi * cphi
    r02 = cpsi * sth * cphi + spsi * sphi

    r10 = spsi * cth
    r11 = spsi * sth * sphi + cpsi * cphi
    r12 = spsi * sth * cphi - cpsi * sphi

    r20 = -sth
    r21 = cth * sphi
    r22 = cth * cphi

    return np.array([[r00, r01, r02], [r10, r11, r12], [r20, r21, r22]], dtype=float)


def wrap_angle(a: float) -> float:
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def minimum_jerk_1d(p0: float, p1: float, T: float, t: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    if T <= 0:
        raise ValueError("Duration T must be positive")
    u = np.clip(t / T, 0.0, 1.0)
    du_dt = 1.0 / T

    s = 10 * u**3 - 15 * u**4 + 6 * u**5
    s_dot = (30 * u**2 - 60 * u**3 + 30 * u**4) * du_dt
    s_ddot = (60 * u - 180 * u**2 + 120 * u**3) * (du_dt**2)

    dp = p1 - p0
    p = p0 + dp * s
    v = dp * s_dot
    a = dp * s_ddot
    return p, v, a


def build_trajectory(start: np.ndarray, end: np.ndarray, yaw: float, T: float, params: Params) -> np.ndarray:
    n = int(round(T * params.sample_rate)) + 1
    t = np.linspace(0.0, T, n)

    pos = np.zeros((3, n))
    vel = np.zeros((3, n))
    acc = np.zeros((3, n))

    for i in range(3):
        pos[i], vel[i], acc[i] = minimum_jerk_1d(float(start[i]), float(end[i]), T, t)

    # Physical acceleration feasibility gate on the planned trajectory.
    az = acc[2]
    if np.any(az > params.accel_limit_up + 1e-9) or np.any(az < -params.accel_limit_down - 1e-9):
        raise ValueError("Planned vertical acceleration violates limits")

    ah = np.linalg.norm(acc[0:2], axis=0)
    if np.any(ah > params.accel_limit_horiz + 1e-9):
        raise ValueError("Planned horizontal acceleration violates limits")

    # Desired attitude feedforward based on feedforward acceleration (small-angle inverse mapping).
    psi = np.full(n, yaw, dtype=float)
    phi = (acc[0] * np.sin(psi) - acc[1] * np.cos(psi)) / params.gravity
    theta = (acc[0] * np.cos(psi) + acc[1] * np.sin(psi)) / params.gravity
    omega = np.zeros((3, n), dtype=float)

    traj = np.zeros((15, n), dtype=float)
    traj[0:3] = pos
    traj[3:6] = vel
    traj[6:9] = np.vstack([phi, theta, psi])
    traj[9:12] = omega
    traj[12:15] = acc
    return traj


def build_hover_trajectory(pos: np.ndarray, yaw: float, T: float, params: Params) -> np.ndarray:
    n = int(round(T * params.sample_rate)) + 1
    traj = np.zeros((15, n), dtype=float)
    traj[0:3] = pos.reshape(3, 1)
    traj[6:9] = np.array([[0.0], [0.0], [yaw]])
    return traj


def parse_command(text: str) -> Tuple[str, np.ndarray, np.ndarray, float]:
    text = text.strip()

    m = re.match(r"^Take\s+off\s+to\s+([0-9.]+)\s*m\s*height\s+in\s+([0-9.]+)\s*seconds$", text, re.IGNORECASE)
    if m:
        h = float(m.group(1))
        T = float(m.group(2))
        return "takeoff", np.array([0.0, 0.0, 0.0]), np.array([0.0, 0.0, h]), T

    m = re.match(r"^Hover\s+at\s+([0-9.]+)\s*m\s*height\s+for\s+([0-9.]+)\s*seconds$", text, re.IGNORECASE)
    if m:
        h = float(m.group(1))
        T = float(m.group(2))
        return "hover", np.array([0.0, 0.0, h]), np.array([0.0, 0.0, h]), T

    m = re.match(r"^Land\s+from\s+([0-9.]+)\s*m\s*height\s+in\s+([0-9.]+)\s*seconds$", text, re.IGNORECASE)
    if m:
        h = float(m.group(1))
        T = float(m.group(2))
        return "land", np.array([0.0, 0.0, h]), np.array([0.0, 0.0, 0.0]), T

    m = re.match(
        r"^Fly\s+from\s*\(\s*([-0-9.]+)\s*,\s*([-0-9.]+)\s*,\s*([-0-9.]+)\s*\)\s+to\s*\(\s*([-0-9.]+)\s*,\s*([-0-9.]+)\s*,\s*([-0-9.]+)\s*\)\s+in\s+([0-9.]+)\s*seconds$",
        text,
        re.IGNORECASE,
    )
    if m:
        p0 = np.array([float(m.group(i)) for i in range(1, 4)], dtype=float)
        p1 = np.array([float(m.group(i)) for i in range(4, 7)], dtype=float)
        T = float(m.group(7))
        return "fly", p0, p1, T

    raise ValueError(f"Unrecognized command: {text!r}")


def make_integral() -> Dict[str, np.ndarray]:
    return {"e": np.zeros(3, dtype=float)}


def position_controller(
    pos: np.ndarray,
    vel: np.ndarray,
    pos_des: np.ndarray,
    vel_des: np.ndarray,
    acc_des: np.ndarray,
    params: Params,
    gains: Dict[str, np.ndarray],
    integral: Dict[str, np.ndarray],
) -> np.ndarray:
    dt = params.dt
    e_p = pos_des - pos
    e_v = vel_des - vel

    integral["e"] = integral["e"] + e_p * dt

    a_cmd = acc_des + gains["kp_pos"] * e_p + gains["kd_pos"] * e_v + gains["ki_pos"] * integral["e"]

    # Clip to physical acceleration limits.
    a_cmd = a_cmd.copy()
    a_cmd[2] = float(np.clip(a_cmd[2], -params.accel_limit_down, params.accel_limit_up))

    horiz = float(np.linalg.norm(a_cmd[0:2]))
    if horiz > params.accel_limit_horiz:
        a_cmd[0:2] *= params.accel_limit_horiz / horiz

    return a_cmd


def attitude_from_accel(ax: float, ay: float, psi: float, g: float) -> Tuple[float, float]:
    phi = (ax * math.sin(psi) - ay * math.cos(psi)) / g
    theta = (ax * math.cos(psi) + ay * math.sin(psi)) / g
    return phi, theta


def attitude_controller(
    rot: np.ndarray,
    omega: np.ndarray,
    rot_des: np.ndarray,
    omega_des: np.ndarray,
    params: Params,
    gains: Dict[str, np.ndarray],
    integral: Dict[str, np.ndarray],
) -> np.ndarray:
    dt = params.dt

    e = rot_des - rot
    e[2] = wrap_angle(float(e[2]))
    integral["e"] = integral["e"] + e * dt

    moment = params.inertia @ (
        gains["kp_att"] * e + gains["ki_att"] * integral["e"] + gains["kd_att"] * (omega_des - omega)
    )

    moment = np.clip(moment, -params.moment_max, params.moment_max)
    return moment


def allocate_rpm(F: float, M: np.ndarray, params: Params) -> np.ndarray:
    cmd = np.array([F, float(M[0]), float(M[1]), float(M[2])], dtype=float)
    rpm_sq = params.prop_matrix_inv @ cmd
    rpm_sq = np.maximum(rpm_sq, 0.0)
    rpm = np.sqrt(rpm_sq)
    rpm = np.clip(rpm, params.rpm_min, params.rpm_max)
    return rpm


def dynamics_derivative(state: np.ndarray, rpm_des: np.ndarray, params: Params) -> np.ndarray:
    pos = state[0:3]
    vel = state[3:6]
    rot = state[6:9]
    omega = state[9:12]
    rpm = state[12:16]

    rpm_dot = params.motor_constant * (rpm_des - rpm)

    F, Mx, My, Mz = params.prop_matrix @ (rpm**2)

    R = rot_matrix_zyx(float(rot[0]), float(rot[1]), float(rot[2]))
    thrust_world = R @ np.array([0.0, 0.0, float(F)], dtype=float)
    acc = thrust_world / params.mass - np.array([0.0, 0.0, params.gravity], dtype=float)

    omega_dot = np.linalg.solve(params.inertia, np.array([Mx, My, Mz], dtype=float))

    d = np.zeros_like(state)
    d[0:3] = vel
    d[3:6] = acc
    d[6:9] = omega  # simplified (matches provided skill contract)
    d[9:12] = omega_dot
    d[12:16] = rpm_dot
    return d


def rk4_step(state: np.ndarray, rpm_des: np.ndarray, params: Params) -> np.ndarray:
    dt = params.dt
    k1 = dynamics_derivative(state, rpm_des, params)
    k2 = dynamics_derivative(state + 0.5 * dt * k1, rpm_des, params)
    k3 = dynamics_derivative(state + 0.5 * dt * k2, rpm_des, params)
    k4 = dynamics_derivative(state + dt * k3, rpm_des, params)
    nxt = state + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)

    # Enforce motor limits.
    nxt[12:16] = np.clip(nxt[12:16], params.rpm_min, params.rpm_max)
    return nxt


def state_to_15(state: np.ndarray, params: Params) -> np.ndarray:
    pos = state[0:3]
    vel = state[3:6]
    rot = state[6:9]
    omega = state[9:12]
    rpm = state[12:16]

    F, _, _, _ = params.prop_matrix @ (rpm**2)
    R = rot_matrix_zyx(float(rot[0]), float(rot[1]), float(rot[2]))
    thrust_world = R @ np.array([0.0, 0.0, float(F)], dtype=float)
    acc = thrust_world / params.mass - np.array([0.0, 0.0, params.gravity], dtype=float)

    out = np.zeros(15, dtype=float)
    out[0:3] = pos
    out[3:6] = vel
    out[6:9] = rot
    out[9:12] = omega
    out[12:15] = acc
    return out


def hover_rpm(params: Params) -> float:
    return float(np.clip(math.sqrt(params.mass * params.gravity / (4.0 * params.thrust_coefficient)), params.rpm_min, params.rpm_max))


def simulate(traj_des: np.ndarray, init_state: np.ndarray, params: Params, gains: Dict[str, np.ndarray]) -> np.ndarray:
    n = traj_des.shape[1]
    actual = np.zeros((15, n), dtype=float)

    pos_int = make_integral()
    att_int = make_integral()

    state = init_state.copy()

    for k in range(n):
        desired = traj_des[:, k]
        pos_des = desired[0:3]
        vel_des = desired[3:6]
        acc_des = desired[12:15]
        psi_des = float(desired[8])

        actual[:, k] = state_to_15(state, params)

        if k == n - 1:
            break

        pos = state[0:3]
        vel = state[3:6]
        rot = state[6:9]
        omega = state[9:12]

        a_cmd = position_controller(pos, vel, pos_des, vel_des, acc_des, params, gains, pos_int)

        phi_cmd, theta_cmd = attitude_from_accel(float(a_cmd[0]), float(a_cmd[1]), psi_des, params.gravity)
        # Mild tilt cap to avoid pathological solutions.
        phi_cmd = float(np.clip(phi_cmd, -0.8, 0.8))
        theta_cmd = float(np.clip(theta_cmd, -0.8, 0.8))

        denom = math.cos(phi_cmd) * math.cos(theta_cmd)
        denom = max(0.2, denom)
        F_cmd = params.mass * (params.gravity + float(a_cmd[2])) / denom
        F_cmd = float(np.clip(F_cmd, params.thrust_min, params.thrust_max))

        rot_des = np.array([phi_cmd, theta_cmd, psi_des], dtype=float)
        omega_des = np.zeros(3, dtype=float)

        M_cmd = attitude_controller(rot, omega, rot_des, omega_des, params, gains, att_int)
        rpm_des = allocate_rpm(F_cmd, M_cmd, params)

        state = rk4_step(state, rpm_des, params)

    return actual


def stepinfo_3d(pos_actual: np.ndarray, pos_target: np.ndarray, t: np.ndarray, settling_threshold: float = 0.02) -> Dict[str, float]:
    dist = np.linalg.norm(pos_actual - pos_target.reshape(3, 1), axis=0)
    d0 = float(dist[0])

    if d0 < 1e-6:
        return {"RiseTime": 0.0, "SettlingTime": 0.0, "Overshoot_pct": 0.0, "SteadyStateError": 0.0}

    rise_idx = None
    for k in range(dist.size):
        if dist[k] <= 0.1 * d0:
            rise_idx = k
            break

    if rise_idx is None:
        rise_time = float(t[-1])
    else:
        rise_time = float(t[rise_idx])

    band = settling_threshold * d0
    last_outside = 0
    for k in range(dist.size - 1, -1, -1):
        if dist[k] > band:
            last_outside = k
            break
    settling_time = float(t[last_outside])

    entry = None
    for k in range(dist.size):
        if dist[k] <= band:
            entry = k
            break

    if entry is None:
        overshoot_pct = 0.0
    else:
        max_post = float(dist[entry:].max())
        overshoot_pct = 100.0 * max_post / d0

    sse = float(dist[-1])

    return {
        "RiseTime": rise_time,
        "SettlingTime": settling_time,
        "Overshoot_pct": overshoot_pct,
        "SteadyStateError": sse,
    }


def plot_quadrotor(state: np.ndarray, state_des: np.ndarray, time_vec: np.ndarray, save_dir: str, sample_rate: float) -> None:
    os.makedirs(save_dir, exist_ok=True)
    dt = 1.0 / sample_rate

    groups = [
        (slice(0, 3), ["x", "y", "z"], "Position"),
        (slice(3, 6), ["vx", "vy", "vz"], "Velocity"),
        (slice(6, 9), [r"$\phi$", r"$\theta$", r"$\psi$"], "Orientation"),
        (slice(9, 12), ["p", "q", "r"], "Angular velocity"),
        (slice(12, 15), ["ax", "ay", "az"], "Acceleration"),
    ]

    def grid_fig(title: str):
        fig, axes = plt.subplots(5, 3, figsize=(16, 20), sharex=True)
        fig.suptitle(title)
        return fig, axes

    fig1, ax1 = grid_fig("Desired vs Actual")
    fig2, ax2 = grid_fig("Errors (actual - desired)")
    fig3, ax3 = grid_fig("Cumulative absolute error")

    for gi, (sl, labels, gname) in enumerate(groups):
        for ai in range(3):
            a = state[sl, :][ai]
            d = state_des[sl, :][ai]
            e = a - d
            c = dt * np.cumsum(np.abs(e))

            ax1[gi, ai].plot(time_vec, d, "b", linewidth=1)
            ax1[gi, ai].plot(time_vec, a, "r", linewidth=1)
            ax1[gi, ai].set_ylabel(f"{gname} {labels[ai]}")

            ax2[gi, ai].plot(time_vec, e, "k", linewidth=1)
            ax2[gi, ai].set_ylabel(f"{gname} {labels[ai]}")

            ax3[gi, ai].plot(time_vec, c, "g", linewidth=1)
            ax3[gi, ai].set_ylabel(f"{gname} {labels[ai]}")

    for axes in [ax1, ax2, ax3]:
        for j in range(3):
            axes[4, j].set_xlabel("time [s]")

    fig1.tight_layout(rect=[0, 0.03, 1, 0.98])
    fig2.tight_layout(rect=[0, 0.03, 1, 0.98])
    fig3.tight_layout(rect=[0, 0.03, 1, 0.98])

    fig1.savefig(os.path.join(save_dir, "desired_vs_actual.png"))
    fig2.savefig(os.path.join(save_dir, "errors.png"))
    fig3.savefig(os.path.join(save_dir, "cumulative_errors.png"))

    plt.close(fig1)
    plt.close(fig2)
    plt.close(fig3)


def evaluate_run(traj_des: np.ndarray, traj_act: np.ndarray) -> Dict[str, float]:
    pos_err = np.linalg.norm(traj_act[0:3] - traj_des[0:3], axis=0)
    return {
        "max_pos_err": float(pos_err.max()),
        "final_pos_err": float(pos_err[-1]),
    }


def tune(traj_des: np.ndarray, init_state: np.ndarray, params: Params, mode: str) -> Tuple[Dict[str, np.ndarray], np.ndarray, Dict[str, float]]:
    base = {
        "kp_pos": np.array([7.0, 7.0, 11.0], dtype=float),
        "ki_pos": np.array([0.08, 0.08, 0.10], dtype=float),
        "kd_pos": np.array([4.5, 4.5, 6.5], dtype=float),
        "kp_att": np.array([220.0, 220.0, 120.0], dtype=float),
        "ki_att": np.array([0.0, 0.0, 0.2], dtype=float),
        "kd_att": np.array([18.0, 18.0, 10.0], dtype=float),
    }

    best = None
    best_score = float("inf")

    gains = {k: v.copy() for k, v in base.items()}

    t = np.arange(traj_des.shape[1], dtype=float) * params.dt
    pos_target = traj_des[0:3, -1]

    for _ in range(8):
        traj_act = simulate(traj_des, init_state, params, gains)
        metrics = stepinfo_3d(traj_act[0:3], pos_target, t, settling_threshold=0.02)
        evald = evaluate_run(traj_des, traj_act)

        max_err = evald["max_pos_err"]
        sse = metrics["SteadyStateError"]
        overshoot = metrics["Overshoot_pct"]

        score = max_err * 2000.0 + max(0.0, overshoot - 5.0) * 50.0 + sse * 500.0

        ok = (max_err < 0.05) and (sse < 0.05) and (overshoot < 5.0)

        if score < best_score:
            best_score = score
            best = ({k: v.copy() for k, v in gains.items()}, traj_act.copy(), {**metrics, **evald})

        if ok:
            break

        if max_err >= 0.05:
            gains["kp_pos"] *= 1.15
            gains["kd_pos"] *= 1.10
            gains["kp_att"] *= 1.10
            gains["kd_att"] *= 1.05

        if overshoot >= 5.0:
            gains["kp_pos"] *= 0.85
            gains["kd_pos"] *= 1.15

        if mode in {"hover", "takeoff", "land"}:
            gains["ki_pos"] *= 0.9

    assert best is not None
    return best[0], best[1], best[2]


def gains_to_jsonable(g: Dict[str, np.ndarray]) -> Dict[str, List[float]]:
    return {
        "kp_pos": [float(x) for x in g["kp_pos"]],
        "ki_pos": [float(x) for x in g["ki_pos"]],
        "kd_pos": [float(x) for x in g["kd_pos"]],
        "kp_att": [float(x) for x in g["kp_att"]],
        "ki_att": [float(x) for x in g["ki_att"]],
        "kd_att": [float(x) for x in g["kd_att"]],
    }


def write_results(
    out_dir: str,
    mode: str,
    traj_des: np.ndarray,
    traj_act: np.ndarray,
    gains: Dict[str, np.ndarray],
    metrics: Dict[str, float],
    params: Params,
) -> None:
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.join(out_dir, "plots"), exist_ok=True)

    np.save(os.path.join(out_dir, "planned_trajectory.npy"), traj_des)
    np.save(os.path.join(out_dir, "actual_trajectory.npy"), traj_act)

    with open(os.path.join(out_dir, "tuning_results.json"), "w", encoding="utf-8") as f:
        json.dump(gains_to_jsonable(gains), f, indent=2)

    metrics_out = {
        "mode": mode,
        "RiseTime": float(metrics["RiseTime"]),
        "SettlingTime": float(metrics["SettlingTime"]),
        "Overshoot_pct": float(metrics["Overshoot_pct"]),
        "SteadyStateError": float(metrics["SteadyStateError"]),
    }

    with open(os.path.join(out_dir, "metrics_3d.json"), "w", encoding="utf-8") as f:
        json.dump(metrics_out, f, indent=2)

    t = np.arange(traj_des.shape[1], dtype=float) * params.dt
    plot_quadrotor(traj_act, traj_des, t, os.path.join(out_dir, "plots"), params.sample_rate)


def main() -> None:
    params = load_params("/root/system_params.yaml")

    cmd_dir = "/root/commands"
    out_root = "/root/results"
    os.makedirs(out_root, exist_ok=True)

    files = sorted([f for f in os.listdir(cmd_dir) if f.endswith(".txt")])

    for fname in files:
        cmd_id = os.path.splitext(fname)[0]
        with open(os.path.join(cmd_dir, fname), "r", encoding="utf-8") as f:
            cmd_text = f.read().strip()

        mode, p0, p1, T = parse_command(cmd_text)

        yaw = 0.0
        if mode == "hover":
            traj_des = build_hover_trajectory(p0, yaw, T, params)
        else:
            traj_des = build_trajectory(p0, p1, yaw, T, params)

        rpm0 = hover_rpm(params)
        init_state = np.zeros(16, dtype=float)
        init_state[0:3] = p0
        init_state[12:16] = rpm0

        gains, traj_act, metrics = tune(traj_des, init_state, params, mode)

        out_dir = os.path.join(out_root, cmd_id)
        write_results(out_dir, mode, traj_des, traj_act, gains, metrics, params)

        # Final guardrails for this command.
        pos_err = np.linalg.norm(traj_act[0:3] - traj_des[0:3], axis=0)
        if float(pos_err.max()) >= 0.05 + 1e-12:
            raise RuntimeError(f"{cmd_id}: max per-timestep position error {pos_err.max():.3f} m")
        if float(metrics["SteadyStateError"]) >= 0.05 + 1e-12:
            raise RuntimeError(f"{cmd_id}: steady-state error {metrics['SteadyStateError']:.3f} m")
        if float(metrics["Overshoot_pct"]) >= 5.0 + 1e-12:
            raise RuntimeError(f"{cmd_id}: overshoot {metrics['Overshoot_pct']:.2f}%")

    print(f"Wrote results to {out_root} for {len(files)} commands")


if __name__ == "__main__":
    main()
