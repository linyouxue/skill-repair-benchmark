from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import numpy as np
import yaml


@dataclass(frozen=True)
class SystemParams:
    sample_rate: float
    dt: float
    mass: float
    gravity: float
    arm_length: float
    motor_spread_angle: float
    thrust_coefficient: float
    moment_scale: float
    motor_constant: float
    rpm_min: float
    rpm_max: float
    inertia: np.ndarray  # (3,3)
    inertia_inv: np.ndarray  # (3,3)

    accel_limit_up: float
    accel_limit_down: float
    accel_limit_horiz: float

    prop_matrix: np.ndarray  # (4,4)


def load_system_params(path: str = "/root/system_params.yaml") -> SystemParams:
    with open(path, "r") as f:
        raw: Dict[str, Any] = yaml.safe_load(f)

    sr = float(raw["sample_rate"])
    dt = 1.0 / sr
    m = float(raw["mass"])
    g = float(raw["gravity"])

    arm = float(raw["arm_length"])
    spread = float(raw["motor_spread_angle"])

    cT = float(raw["thrust_coefficient"])
    cQ = float(raw["moment_scale"])

    km = float(raw["motor_constant"])
    rpm_min = float(raw["rpm_min"])
    rpm_max = float(raw["rpm_max"])

    inertia_diag = np.array(raw["inertia"], dtype=float).reshape(3)
    I = np.diag(inertia_diag)
    Iinv = np.linalg.inv(I)

    d_eff = arm * np.sin(spread)

    prop = np.array(
        [
            [cT, cT, cT, cT],
            [0.0, d_eff * cT, 0.0, -d_eff * cT],
            [-d_eff * cT, 0.0, d_eff * cT, 0.0],
            [-cQ, cQ, -cQ, cQ],
        ],
        dtype=float,
    )

    return SystemParams(
        sample_rate=sr,
        dt=dt,
        mass=m,
        gravity=g,
        arm_length=arm,
        motor_spread_angle=spread,
        thrust_coefficient=cT,
        moment_scale=cQ,
        motor_constant=km,
        rpm_min=rpm_min,
        rpm_max=rpm_max,
        inertia=I,
        inertia_inv=Iinv,
        accel_limit_up=float(raw["accel_limit_up"]),
        accel_limit_down=float(raw["accel_limit_down"]),
        accel_limit_horiz=float(raw["accel_limit_horiz"]),
        prop_matrix=prop,
    )
