from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import numpy as np
import yaml


@dataclass(frozen=True)
class DroneParams:
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
    inertia: np.ndarray
    COM_vertical_offset: float
    accel_limit_up: float
    accel_limit_down: float
    accel_limit_horiz: float


def load_params(path: str | Path = "/root/system_params.yaml") -> DroneParams:
    p = Path(path)
    data: Dict[str, Any]
    with p.open("r") as f:
        data = yaml.safe_load(f)

    inertia_diag = np.asarray(data["inertia"], dtype=float)
    inertia = np.diag(inertia_diag)

    return DroneParams(
        sample_rate=float(data["sample_rate"]),
        mass=float(data["mass"]),
        gravity=float(data["gravity"]),
        arm_length=float(data["arm_length"]),
        motor_spread_angle=float(data["motor_spread_angle"]),
        thrust_coefficient=float(data["thrust_coefficient"]),
        moment_scale=float(data["moment_scale"]),
        motor_constant=float(data["motor_constant"]),
        rpm_min=float(data["rpm_min"]),
        rpm_max=float(data["rpm_max"]),
        inertia=inertia,
        COM_vertical_offset=float(data["COM_vertical_offset"]),
        accel_limit_up=float(data["accel_limit_up"]),
        accel_limit_down=float(data["accel_limit_down"]),
        accel_limit_horiz=float(data["accel_limit_horiz"]),
    )
