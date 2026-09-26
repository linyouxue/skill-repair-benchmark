from __future__ import annotations

import numpy as np


def prop_matrix(params: dict) -> np.ndarray:
    cT = float(params["thrust_coefficient"])
    cQ = float(params["moment_scale"])
    d = float(params["arm_length"])
    a = float(params["motor_spread_angle"])

    # Motor positions in body frame (x forward, y left)
    # 1: +x,+y ; 2: -x,+y ; 3: -x,-y ; 4: +x,-y
    x = d * np.cos(a)
    y = d * np.sin(a)
    r = np.array(
        [
            [x, y, 0.0],
            [-x, y, 0.0],
            [-x, -y, 0.0],
            [x, -y, 0.0],
        ],
        dtype=float,
    )

    # Fz thrust along +body z
    # Moments from thrust: M = r x [0,0,T] => [y*T, -x*T, 0]
    Mx = r[:, 1] * cT
    My = -r[:, 0] * cT

    # Yaw torque signs (1&3 opposite of 2&4)
    yaw_sign = np.array([-1.0, 1.0, -1.0, 1.0], dtype=float)

    A = np.zeros((4, 4), dtype=float)
    A[0, :] = cT
    A[1, :] = Mx
    A[2, :] = My
    A[3, :] = yaw_sign * cQ
    return A


def motor_model(params: dict, u: np.ndarray, motor_rpm: np.ndarray) -> tuple[float, np.ndarray, np.ndarray, np.ndarray]:
    """Map desired [F,Mx,My,Mz] to motor RPMs, apply lag, return actual F and M.

    Returns: (F_actual, M_actual(3,), rpm_dot(4,), rpm_des(4,))
    """

    A = prop_matrix(params)
    rpm_min = float(params["rpm_min"])
    rpm_max = float(params["rpm_max"])
    km = float(params["motor_constant"])

    u = np.array(u, dtype=float).reshape(4)
    try:
        rpm_sq_des = np.linalg.solve(A, u)
    except np.linalg.LinAlgError:
        rpm_sq_des = np.linalg.pinv(A) @ u

    rpm_sq_des = np.clip(rpm_sq_des, 0.0, None)
    rpm_des = np.sqrt(rpm_sq_des)
    rpm_des = np.clip(rpm_des, rpm_min, rpm_max)

    motor_rpm = np.array(motor_rpm, dtype=float).reshape(4)
    rpm_dot = km * (rpm_des - motor_rpm)

    # Actual force/moments based on current rpm (not yet advanced)
    u_actual = A @ (motor_rpm**2)
    F_actual = float(u_actual[0])
    M_actual = np.array(u_actual[1:4], dtype=float)

    return F_actual, M_actual, rpm_dot, rpm_des
