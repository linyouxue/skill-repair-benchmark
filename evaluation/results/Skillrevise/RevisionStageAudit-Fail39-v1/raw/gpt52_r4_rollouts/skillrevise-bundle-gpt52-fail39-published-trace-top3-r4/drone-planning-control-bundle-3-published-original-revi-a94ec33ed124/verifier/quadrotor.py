from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np

from math_utils import body_rates_to_euler_rates, euler_to_R
from params import SystemParams


@dataclass
class QuadrotorState:
    pos: np.ndarray  # (3,)
    vel: np.ndarray  # (3,)
    euler: np.ndarray  # (3,) roll,pitch,yaw
    omega: np.ndarray  # (3,) body rates p,q,r
    motor_rpm: np.ndarray  # (4,)


def motor_geometry(params: SystemParams) -> Tuple[np.ndarray, np.ndarray]:
    a = params.motor_spread_angle
    L = params.arm_length
    angles = np.array([a, np.pi - a, np.pi + a, -a], dtype=float)
    r = np.stack([L * np.cos(angles), L * np.sin(angles), np.zeros(4)], axis=1)
    spin_dir = np.array([1.0, -1.0, 1.0, -1.0], dtype=float)
    return r, spin_dir


def allocation_matrix(params: SystemParams) -> np.ndarray:
    r, spin_dir = motor_geometry(params)
    kf = params.thrust_coefficient
    km = params.moment_scale

    A = np.zeros((4, 4), dtype=float)
    A[0, :] = kf
    A[1, :] = kf * r[:, 1]
    A[2, :] = -kf * r[:, 0]
    A[3, :] = km * spin_dir
    return A


def mix_to_rpm(thrust: float, moment: np.ndarray, params: SystemParams) -> np.ndarray:
    cmd = np.array([thrust, moment[0], moment[1], moment[2]], dtype=float)
    A = allocation_matrix(params)
    u = np.linalg.solve(A, cmd)

    u = np.clip(u, params.rpm_min**2, params.rpm_max**2)
    return np.sqrt(u)


def forces_and_moments_from_rpm(rpm: np.ndarray, params: SystemParams) -> Tuple[float, np.ndarray]:
    r, spin_dir = motor_geometry(params)
    kf = params.thrust_coefficient
    km = params.moment_scale

    u = rpm**2
    thrusts = kf * u
    T = float(np.sum(thrusts))

    tau_x = float(np.sum(r[:, 1] * thrusts))
    tau_y = float(np.sum(-r[:, 0] * thrusts))
    tau_z = float(np.sum(km * spin_dir * u))
    return T, np.array([tau_x, tau_y, tau_z], dtype=float)


def step_dynamics(
    state: QuadrotorState,
    rpm_cmd: np.ndarray,
    params: SystemParams,
    dt: float,
) -> Tuple[QuadrotorState, np.ndarray]:
    rpm = state.motor_rpm + dt * params.motor_constant * (rpm_cmd - state.motor_rpm)
    rpm = np.clip(rpm, params.rpm_min, params.rpm_max)

    T, M = forces_and_moments_from_rpm(rpm, params)

    R = euler_to_R(float(state.euler[0]), float(state.euler[1]), float(state.euler[2]))
    e3 = np.array([0.0, 0.0, 1.0], dtype=float)

    acc_world = (T / params.mass) * (R @ e3) - params.gravity * e3

    omega = state.omega
    I = params.inertia
    omega_dot = np.linalg.solve(I, M - np.cross(omega, I @ omega))

    vel = state.vel + dt * acc_world
    pos = state.pos + dt * vel

    omega_new = omega + dt * omega_dot
    euler_dot = body_rates_to_euler_rates(state.euler, omega_new)
    euler_new = state.euler + dt * euler_dot

    new_state = QuadrotorState(
        pos=pos,
        vel=vel,
        euler=euler_new,
        omega=omega_new,
        motor_rpm=rpm,
    )
    return new_state, acc_world


def initial_state(pos0: np.ndarray, params: SystemParams) -> QuadrotorState:
    hover_rpm = np.sqrt(params.mass * params.gravity / (4.0 * params.thrust_coefficient))
    hover_rpm = float(np.clip(hover_rpm, params.rpm_min, params.rpm_max))
    return QuadrotorState(
        pos=pos0.astype(float),
        vel=np.zeros(3, dtype=float),
        euler=np.zeros(3, dtype=float),
        omega=np.zeros(3, dtype=float),
        motor_rpm=np.full(4, hover_rpm, dtype=float),
    )
