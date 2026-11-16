from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import numpy as np
import yaml


@dataclass(frozen=True)
class SystemParams:
    sample_rate: float
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
    COM_vertical_offset: float
    accel_limit_up: float
    accel_limit_down: float
    accel_limit_horiz: float


def load_system_params(path: str = "/root/system_params.yaml") -> SystemParams:
    with open(path, "r", encoding="utf-8") as f:
        raw: Dict[str, Any] = yaml.safe_load(f)

    inertia_diag = np.array(raw["inertia"], dtype=float)
    return SystemParams(
        sample_rate=float(raw["sample_rate"]),
        mass=float(raw["mass"]),
        gravity=float(raw["gravity"]),
        arm_length=float(raw["arm_length"]),
        motor_spread_angle=float(raw["motor_spread_angle"]),
        thrust_coefficient=float(raw["thrust_coefficient"]),
        moment_scale=float(raw["moment_scale"]),
        motor_constant=float(raw["motor_constant"]),
        rpm_min=float(raw["rpm_min"]),
        rpm_max=float(raw["rpm_max"]),
        inertia=np.diag(inertia_diag),
        COM_vertical_offset=float(raw["COM_vertical_offset"]),
        accel_limit_up=float(raw["accel_limit_up"]),
        accel_limit_down=float(raw["accel_limit_down"]),
        accel_limit_horiz=float(raw["accel_limit_horiz"]),
    )
