from __future__ import annotations

from typing import Tuple

import numpy as np


def prop_allocation_matrix(params: dict) -> np.ndarray:
    """Return 4x4 allocation matrix mapping rpm^2 -> [F, Mx, My, Mz]."""

    cT = float(params["thrust_coefficient"])
    cQ = float(params["moment_scale"])
    d = float(params["arm_length"])

    return np.array(
        [
            [cT, cT, cT, cT],
            [0.0, d * cT, 0.0, -d * cT],
            [-d * cT, 0.0, d * cT, 0.0],
            [-cQ, cQ, -cQ, cQ],
        ],
        dtype=float,
    )


def motor_model(
    params: dict,
    motor_rpm: np.ndarray,
    F_des: float,
    M_des: np.ndarray,
) -> Tuple[float, np.ndarray, np.ndarray]:
    """Compute actual force/moment and motor rpm_dot.

    Args:
        motor_rpm: (4,) current rpm
        F_des: desired thrust [N]
        M_des: (3,) desired moments [N*m]

    Returns:
        F_actual: float
        M_actual: (3,)
        rpm_dot: (4,)
    """

    motor_rpm = np.asarray(motor_rpm, dtype=float).reshape(4)
    M_des = np.asarray(M_des, dtype=float).reshape(3)

    km = float(params["motor_constant"])
    rpm_min = float(params["rpm_min"])
    rpm_max = float(params["rpm_max"])

    prop = prop_allocation_matrix(params)
    u = np.array([float(F_des), float(M_des[0]), float(M_des[1]), float(M_des[2])], dtype=float)

    rpm_sq_des = np.linalg.solve(prop, u)
    rpm_sq_des = np.maximum(rpm_sq_des, 0.0)
    rpm_des = np.sqrt(rpm_sq_des)
    rpm_des = np.clip(rpm_des, rpm_min, rpm_max)

    rpm_dot = km * (rpm_des - motor_rpm)

    forces = prop @ (motor_rpm**2)
    F_actual = float(forces[0])
    M_actual = forces[1:4]
    return F_actual, M_actual, rpm_dot
