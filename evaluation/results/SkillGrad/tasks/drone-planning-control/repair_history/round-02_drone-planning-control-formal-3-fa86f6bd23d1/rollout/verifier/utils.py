from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml


PARAMS_PATH = Path('/root/system_params.yaml')


def load_params(path: str | Path = PARAMS_PATH) -> dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        params = yaml.safe_load(f)

    params['inertia_matrix'] = np.diag(np.asarray(params['inertia'], dtype=float))

    cT = float(params['thrust_coefficient'])
    rpm_min = float(params['rpm_min'])
    rpm_max = float(params['rpm_max'])
    params['thrust_min'] = 4.0 * cT * rpm_min**2
    params['thrust_max'] = 4.0 * cT * rpm_max**2

    return params


def clamp_norm_2d(v: np.ndarray, max_norm: float) -> np.ndarray:
    n = float(np.linalg.norm(v))
    if n <= max_norm or n < 1e-12:
        return v
    return v * (max_norm / n)


def wrap_angle_pi(a: float) -> float:
    return (a + np.pi) % (2 * np.pi) - np.pi


@dataclass
class DesiredState:
    pos: np.ndarray  # (3,)
    vel: np.ndarray  # (3,)
    rot: np.ndarray  # (3,) euler [phi, theta, psi]
    omega: np.ndarray  # (3,)
    acc: np.ndarray  # (3,)


@dataclass
class CurrentState:
    pos: np.ndarray  # (3,)
    vel: np.ndarray  # (3,)
    rot: np.ndarray  # (3,)
    omega: np.ndarray  # (3,)
    rpm: np.ndarray  # (4,)


def make_position_integral() -> dict[str, np.ndarray]:
    return {'e': np.zeros(3, dtype=float)}


def make_attitude_integral() -> dict[str, np.ndarray]:
    return {'e': np.zeros(3, dtype=float)}
