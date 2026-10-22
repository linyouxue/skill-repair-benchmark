import numpy as np


def attitude_planner(acc_des: np.ndarray, yaw_des: float, yaw_rate_des: float, gravity: float):
    acc_des = np.array(acc_des, dtype=float).reshape(3)
    psi = float(yaw_des)

    a_total = acc_des + np.array([0.0, 0.0, float(gravity)], dtype=float)
    n = float(np.linalg.norm(a_total))
    if n < 1e-9:
        b3 = np.array([0.0, 0.0, 1.0], dtype=float)
    else:
        b3 = a_total / n

    b1_des = np.array([np.cos(psi), np.sin(psi), 0.0], dtype=float)
    b2 = np.cross(b3, b1_des)
    b2_n = float(np.linalg.norm(b2))
    if b2_n < 1e-9:
        b2 = np.array([-np.sin(psi), np.cos(psi), 0.0], dtype=float)
    else:
        b2 = b2 / b2_n

    b1 = np.cross(b2, b3)
    R = np.column_stack([b1, b2, b3])

    # ZYX Euler extraction
    theta = float(np.arcsin(np.clip(-R[2, 0], -1.0, 1.0)))
    phi = float(np.arctan2(R[2, 1], R[2, 2]))

    rot_des = np.array([phi, theta, psi], dtype=float)
    omega_des = np.array([0.0, 0.0, float(yaw_rate_des)], dtype=float)
    return rot_des, omega_des
