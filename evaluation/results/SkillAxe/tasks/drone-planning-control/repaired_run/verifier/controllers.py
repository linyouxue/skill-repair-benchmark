import numpy as np


def make_position_integral() -> dict:
    return {"e": np.zeros(3, dtype=float)}


def position_controller(
    current_pos: np.ndarray,
    current_vel: np.ndarray,
    desired_pos: np.ndarray,
    desired_vel: np.ndarray,
    desired_acc: np.ndarray,
    params: dict,
    gains: dict,
    integral: dict,
) -> tuple[float, np.ndarray]:
    dt = float(params["dt"])

    pos_err = current_pos - desired_pos
    vel_err = current_vel - desired_vel

    integral["e"] = integral["e"] + pos_err * dt

    kp = np.array(gains["kp_pos"], dtype=float)
    ki = np.array(gains["ki_pos"], dtype=float)
    kd = np.array(gains["kd_pos"], dtype=float)

    acc_cmd = desired_acc - kp * pos_err - ki * integral["e"] - kd * vel_err

    m = float(params["mass"])
    g = float(params["gravity"])
    F = m * (g + acc_cmd[2])

    return float(F), acc_cmd


def make_attitude_integral() -> dict:
    return {"e": np.zeros(3, dtype=float)}


def attitude_planner(desired_acc: np.ndarray, desired_yaw: float, params: dict) -> tuple[np.ndarray, np.ndarray]:
    g = float(params["gravity"])
    ax, ay = float(desired_acc[0]), float(desired_acc[1])
    psi = float(desired_yaw)

    phi_des = (ax * np.sin(psi) - ay * np.cos(psi)) / g
    theta_des = (ax * np.cos(psi) + ay * np.sin(psi)) / g

    rot = np.array([phi_des, theta_des, psi], dtype=float)
    omega = np.array([0.0, 0.0, 0.0], dtype=float)
    return rot, omega


def attitude_controller(
    current_rot: np.ndarray,
    current_omega: np.ndarray,
    desired_rot: np.ndarray,
    desired_omega: np.ndarray,
    params: dict,
    gains: dict,
    integral: dict,
) -> np.ndarray:
    dt = float(params["dt"])
    I = params["inertia_matrix"]

    e = desired_rot - current_rot
    integral["e"] = integral["e"] + e * dt

    kp = np.array(gains["kp_att"], dtype=float)
    ki = np.array(gains["ki_att"], dtype=float)
    kd = np.array(gains["kd_att"], dtype=float)

    u = kp * e + ki * integral["e"] + kd * (desired_omega - current_omega)
    M = I @ u
    return M
