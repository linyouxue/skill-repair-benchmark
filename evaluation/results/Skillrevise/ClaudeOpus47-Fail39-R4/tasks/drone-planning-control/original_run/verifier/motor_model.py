import numpy as np


def _motor_positions(arm_length: float, motor_spread_angle: float):
    a = float(motor_spread_angle)
    l = float(arm_length)
    # motor positions in body XY plane
    # 1: (+x,+y), 2: (-x,+y), 3: (-x,-y), 4: (+x,-y)
    x = l * np.cos(a)
    y = l * np.sin(a)
    return np.array(
        [
            [x, y],
            [-x, y],
            [-x, -y],
            [x, -y],
        ],
        dtype=float,
    )


def allocation_matrix(params: dict) -> np.ndarray:
    cT = float(params['thrust_coefficient'])
    cQ = float(params['moment_scale'])
    arm = float(params['arm_length'])
    ang = float(params['motor_spread_angle'])

    xy = _motor_positions(arm, ang)

    A = np.zeros((4, 4), dtype=float)
    # Thrust row
    A[0, :] = cT

    # Roll moment about x: Mx = sum(y_i * T_i)
    A[1, :] = xy[:, 1] * cT

    # Pitch moment about y: My = sum(-x_i * T_i)
    A[2, :] = -xy[:, 0] * cT

    # Yaw moment: alternating signs
    A[3, :] = np.array([-cQ, +cQ, -cQ, +cQ], dtype=float)
    return A


def motor_model(params: dict, F_des: float, M_des: np.ndarray, motor_rpm: np.ndarray):
    km = float(params['motor_constant'])
    rpm_min = float(params['rpm_min'])
    rpm_max = float(params['rpm_max'])

    A = allocation_matrix(params)
    u = np.array([float(F_des), float(M_des[0]), float(M_des[1]), float(M_des[2])], dtype=float)

    rpm_sq_des = np.linalg.solve(A, u)
    rpm_sq_des = np.maximum(rpm_sq_des, 0.0)
    rpm_des = np.sqrt(rpm_sq_des)
    rpm_des = np.clip(rpm_des, rpm_min, rpm_max)

    rpm_dot = km * (rpm_des - motor_rpm)
    return rpm_des, rpm_dot


def thrust_moment_from_rpm(params: dict, motor_rpm: np.ndarray):
    A = allocation_matrix(params)
    u = A @ (motor_rpm**2)
    F = float(u[0])
    M = np.array(u[1:4], dtype=float)
    return F, M
