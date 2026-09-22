"""Quadrotor planning, control, motor, and dynamics simulation utilities."""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import matplotlib.pyplot as plt
import numpy as np
import yaml


PARAMETER_FILE = Path(__file__).with_name("system_params.yaml")


def load_params(path: str | os.PathLike[str] = PARAMETER_FILE) -> dict:
    """Load the simulator parameters and derive useful physical limits."""
    with open(path, encoding="utf-8") as handle:
        params = yaml.safe_load(handle)
    params = dict(params)
    params["inertia_matrix"] = np.diag(np.asarray(params["inertia"], dtype=float))
    params["sample_rate"] = float(params["sample_rate"])
    params["dt"] = 1.0 / params["sample_rate"]
    params["mass"] = float(params["mass"])
    params["gravity"] = float(params["gravity"])
    params["arm_length"] = float(params["arm_length"])
    params["thrust_coefficient"] = float(params["thrust_coefficient"])
    params["moment_scale"] = float(params["moment_scale"])
    params["motor_constant"] = float(params["motor_constant"])
    params["rpm_min"] = float(params["rpm_min"])
    params["rpm_max"] = float(params["rpm_max"])
    params["thrust_min"] = 4.0 * params["thrust_coefficient"] * params["rpm_min"] ** 2
    params["thrust_max"] = 4.0 * params["thrust_coefficient"] * params["rpm_max"] ** 2
    params["hover_rpm"] = math.sqrt(
        params["mass"] * params["gravity"] / (4.0 * params["thrust_coefficient"])
    )
    return params


_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"


@dataclass
class FlightPlan:
    waypoints: np.ndarray
    waypoint_times: np.ndarray
    modes: list[str]


class FlightPlanParser:
    """Parse the four supported command forms into a time-ordered plan."""

    takeoff_re = re.compile(
        rf"take\s+off\s+to\s+({_NUMBER})\s*m\s+height\s+in\s+({_NUMBER})\s+seconds?",
        re.IGNORECASE,
    )
    hover_re = re.compile(
        rf"hover\s+at\s+({_NUMBER})\s*m\s+height\s+for\s+({_NUMBER})\s+seconds?",
        re.IGNORECASE,
    )
    land_re = re.compile(
        rf"land\s+from\s+({_NUMBER})\s*m\s+height\s+in\s+({_NUMBER})\s+seconds?",
        re.IGNORECASE,
    )
    fly_re = re.compile(
        rf"fly\s+from\s*\(\s*({_NUMBER})\s*,\s*({_NUMBER})\s*,\s*({_NUMBER})\s*\)"
        rf"\s+to\s*\(\s*({_NUMBER})\s*,\s*({_NUMBER})\s*,\s*({_NUMBER})\s*\)"
        rf"\s+in\s+({_NUMBER})\s+seconds?",
        re.IGNORECASE,
    )

    def __init__(self) -> None:
        self.positions: list[np.ndarray] = []
        self.times: list[float] = []
        self.modes: list[str] = []
        self.current = np.zeros(3, dtype=float)
        self.time = 0.0

    def _start(self, position: Sequence[float]) -> None:
        self.positions = [np.asarray(position, dtype=float).copy()]
        self.times = [0.0]
        self.current = np.asarray(position, dtype=float).copy()
        self.time = 0.0

    def _append(self, position: Sequence[float], duration: float, mode: str) -> None:
        duration = float(duration)
        if duration <= 0.0:
            raise ValueError("segment duration must be positive")
        self.time += duration
        self.current = np.asarray(position, dtype=float).copy()
        self.positions.append(self.current.copy())
        self.times.append(self.time)
        self.modes.append(mode)

    def add_line(self, line: str) -> None:
        text = line.strip()
        if not text:
            return
        match = self.takeoff_re.fullmatch(text)
        if match:
            height, duration = map(float, match.groups())
            if not self.positions:
                self._start((0.0, 0.0, 0.0))
            self._append((self.current[0], self.current[1], height), duration, "takeoff")
            return
        match = self.hover_re.fullmatch(text)
        if match:
            height, duration = map(float, match.groups())
            # A standalone hover command starts with the vehicle already at
            # the requested altitude; this makes it a genuine hold segment.
            if not self.positions:
                self._start((0.0, 0.0, height))
            else:
                self.current[2] = height
                self.positions[-1] = self.current.copy()
            self._append(self.current, duration, "hover")
            return
        match = self.land_re.fullmatch(text)
        if match:
            height, duration = map(float, match.groups())
            if not self.positions:
                self._start((0.0, 0.0, height))
            else:
                self.current[2] = height
                self.positions[-1] = self.current.copy()
            self._append((self.current[0], self.current[1], 0.0), duration, "land")
            return
        match = self.fly_re.fullmatch(text)
        if match:
            values = np.asarray(list(map(float, match.groups())), dtype=float)
            start, end, duration = values[:3], values[3:6], values[6]
            if not self.positions:
                self._start(start)
            elif np.linalg.norm(self.current - start) > 1e-9:
                raise ValueError("fly segment start does not match current position")
            self._append(end, duration, "fly")
            return
        raise ValueError(f"unsupported flight command: {line!r}")

    def plan(self) -> FlightPlan:
        if not self.positions:
            raise ValueError("flight plan contains no commands")
        points = np.zeros((4, len(self.positions)), dtype=float)
        points[:3] = np.asarray(self.positions, dtype=float).T
        return FlightPlan(points, np.asarray(self.times, dtype=float), list(self.modes))


def parse_flight_plan(text: str) -> tuple[np.ndarray, np.ndarray, list[str]]:
    parser = FlightPlanParser()
    for line in text.splitlines():
        parser.add_line(line)
    plan = parser.plan()
    return plan.waypoints, plan.waypoint_times, plan.modes


def make_position_integral() -> dict[str, np.ndarray]:
    return {"e": np.zeros(3, dtype=float)}


def make_attitude_integral() -> dict[str, np.ndarray]:
    return {"e": np.zeros(3, dtype=float)}


def _smoothstep(tau: float, duration: float) -> tuple[float, float, float]:
    if duration <= 0.0:
        return 1.0, 0.0, 0.0
    s = np.clip(tau / duration, 0.0, 1.0)
    return (
        3.0 * s * s - 2.0 * s * s * s,
        (6.0 * s - 6.0 * s * s) / duration,
        (6.0 - 12.0 * s) / duration**2,
    )


def _segment_acceleration_bound(delta: np.ndarray, duration: float) -> tuple[float, float]:
    peak = 6.0 * np.abs(delta) / duration**2
    return float(peak[2]), float(np.linalg.norm(peak[:2]))


def trajectory_planner(
    waypoints: np.ndarray,
    max_iter: int,
    waypoint_times: np.ndarray,
    sample_rate: float,
    modes: Sequence[str],
    params: dict | None = None,
) -> np.ndarray:
    """Generate a complete 15-row, zero-endpoint-velocity trajectory."""
    waypoints = np.asarray(waypoints, dtype=float)
    waypoint_times = np.asarray(waypoint_times, dtype=float)
    if waypoints.shape[0] != 4 or waypoints.shape[1] != len(waypoint_times):
        raise ValueError("waypoints must have shape (4, number_of_times)")
    if len(modes) != waypoints.shape[1] - 1:
        raise ValueError("one mode is required for each waypoint segment")
    if np.any(np.diff(waypoint_times) <= 0.0):
        raise ValueError("waypoint times must be strictly increasing")

    dt = 1.0 / float(sample_rate)
    trajectory = np.zeros((15, int(max_iter)), dtype=float)
    for k in range(int(max_iter)):
        t = k * dt
        if t >= waypoint_times[-1]:
            segment = len(modes) - 1
            tau = waypoint_times[-1] - waypoint_times[-2]
            at_end = True
        else:
            segment = int(np.searchsorted(waypoint_times, t, side="right") - 1)
            segment = int(np.clip(segment, 0, len(modes) - 1))
            tau = t - waypoint_times[segment]
            at_end = False
        p0 = waypoints[:3, segment]
        p1 = waypoints[:3, segment + 1]
        duration = waypoint_times[segment + 1] - waypoint_times[segment]
        mode = modes[segment].lower()
        if mode == "hover" and np.linalg.norm(p1 - p0) < 1e-12:
            position = p0
            velocity = np.zeros(3)
            acceleration = np.zeros(3)
        else:
            s, ds, dds = _smoothstep(tau, duration)
            delta = p1 - p0
            position = p0 + delta * s
            velocity = delta * ds
            acceleration = delta * dds
        if at_end:
            position = p1.copy()
            velocity = np.zeros(3)
            acceleration = np.zeros(3)
        yaw0, yaw1 = waypoints[3, segment], waypoints[3, segment + 1]
        sy, _, _ = _smoothstep(tau, duration)
        yaw = yaw0 + (yaw1 - yaw0) * sy
        trajectory[0:3, k] = position
        trajectory[3:6, k] = velocity
        trajectory[6:9, k] = (0.0, 0.0, yaw)
        trajectory[9:12, k] = 0.0
        trajectory[12:15, k] = acceleration

    if params is not None:
        vertical_up = float(params["accel_limit_up"])
        vertical_down = float(params["accel_limit_down"])
        horizontal = float(params["accel_limit_horiz"])
        a = trajectory[12:15]
        if np.max(a[2]) > vertical_up + 1e-8:
            raise ValueError("planned upward acceleration exceeds configured limit")
        if np.min(a[2]) < -vertical_down - 1e-8:
            raise ValueError("planned downward acceleration exceeds configured limit")
        if np.max(np.linalg.norm(a[:2], axis=0)) > horizontal + 1e-8:
            raise ValueError("planned horizontal acceleration exceeds configured limit")
    return trajectory


def _wrap_angle(angle: np.ndarray) -> np.ndarray:
    return (angle + np.pi) % (2.0 * np.pi) - np.pi


def position_controller(
    current_state: np.ndarray,
    desired_state: np.ndarray,
    params: dict,
    integral: dict[str, np.ndarray],
    gains: dict[str, Sequence[float]] | None = None,
) -> tuple[float, np.ndarray, np.ndarray]:
    """Outer PID: return feasible thrust, acceleration, and world force."""
    gains = gains or gains_for_simulation()
    dt = params["dt"]
    kp = np.asarray(gains["kp_pos"], dtype=float)
    ki = np.asarray(gains["ki_pos"], dtype=float)
    kd = np.asarray(gains["kd_pos"], dtype=float)
    e_pos = desired_state[0:3] - current_state[0:3]
    e_vel = desired_state[3:6] - current_state[3:6]
    integral["e"] += e_pos * dt
    integral["e"] = np.clip(integral["e"], -2.0, 2.0)
    acceleration = desired_state[12:15] + kp * e_pos + kd * e_vel + ki * integral["e"]
    acceleration[2] = np.clip(
        acceleration[2], -params["accel_limit_down"], params["accel_limit_up"]
    )
    horizontal_norm = np.linalg.norm(acceleration[:2])
    if horizontal_norm > params["accel_limit_horiz"]:
        acceleration[:2] *= params["accel_limit_horiz"] / horizontal_norm
    force_world = params["mass"] * (acceleration + np.array([0.0, 0.0, params["gravity"]]))
    force_norm = np.linalg.norm(force_world)
    if force_norm > params["thrust_max"]:
        force_world *= params["thrust_max"] / force_norm
        acceleration = force_world / params["mass"] - np.array([0.0, 0.0, params["gravity"]])
    thrust = float(np.clip(np.linalg.norm(force_world), params["thrust_min"], params["thrust_max"]))
    return thrust, acceleration, force_world


def rotation_matrix(euler: Sequence[float]) -> np.ndarray:
    phi, theta, psi = np.asarray(euler, dtype=float)
    cp, sp = math.cos(phi), math.sin(phi)
    ct, st = math.cos(theta), math.sin(theta)
    cy, sy = math.cos(psi), math.sin(psi)
    rx = np.array(((1.0, 0.0, 0.0), (0.0, cp, -sp), (0.0, sp, cp)))
    ry = np.array(((ct, 0.0, st), (0.0, 1.0, 0.0), (-st, 0.0, ct)))
    rz = np.array(((cy, -sy, 0.0), (sy, cy, 0.0), (0.0, 0.0, 1.0)))
    return rz @ ry @ rx


def attitude_planner(force_world: np.ndarray, yaw: float = 0.0) -> np.ndarray:
    """Find ZYX roll and pitch whose body +z points along world force."""
    force_world = np.asarray(force_world, dtype=float)
    direction = force_world / max(np.linalg.norm(force_world), 1e-12)
    cy, sy = math.cos(yaw), math.sin(yaw)
    # Desired body-z vector for a specified yaw, solved from Rz Ry Rx.
    lateral_x = cy * direction[0] + sy * direction[1]
    lateral_y = sy * direction[0] - cy * direction[1]
    phi = math.asin(np.clip(lateral_y, -1.0, 1.0))
    theta = math.atan2(lateral_x, max(direction[2], 1e-9))
    return np.array([phi, theta, yaw], dtype=float)


def attitude_controller(
    current_state: np.ndarray,
    desired_angles: np.ndarray,
    params: dict,
    integral: dict[str, np.ndarray],
    gains: dict[str, Sequence[float]] | None = None,
) -> np.ndarray:
    gains = gains or gains_for_simulation()
    dt = params["dt"]
    kp = np.asarray(gains["kp_att"], dtype=float)
    ki = np.asarray(gains["ki_att"], dtype=float)
    kd = np.asarray(gains["kd_att"], dtype=float)
    error = _wrap_angle(np.asarray(desired_angles) - current_state[6:9])
    integral["e"] += error * dt
    integral["e"] = np.clip(integral["e"], -0.5, 0.5)
    # Desired Euler rates are zero for the smooth trajectories generated here.
    moments = kp * error - kd * current_state[9:12] + ki * integral["e"]
    return np.clip(moments, -np.array([0.25, 0.25, 0.12]), np.array([0.25, 0.25, 0.12]))


class MotorModel:
    """RPM-space actuator allocation and first-order motor response."""

    def __init__(self, params: dict):
        self.params = params
        a = params["arm_length"] / math.sqrt(2.0)
        ct = params["thrust_coefficient"]
        cq = params["moment_scale"]
        self.a = a
        self.allocation = np.array(
            [
                [ct, ct, ct, ct],
                [a * ct, -a * ct, -a * ct, a * ct],
                [-a * ct, -a * ct, a * ct, a * ct],
                [cq, -cq, cq, -cq],
            ],
            dtype=float,
        )
        self.rpm_min = params["rpm_min"]
        self.rpm_max = params["rpm_max"]

    def wrench_to_rpm(self, wrench: Sequence[float]) -> np.ndarray:
        # The closed-form inverse is equivalent to solve(A, b), but the
        # explicit equations make the motor sign convention unambiguous.
        force, mx, my, mz = np.asarray(wrench, dtype=float)
        ct, cq, a = self.params["thrust_coefficient"], self.params["moment_scale"], self.a
        squared = np.array(
            [
                force / (4 * ct) + mx / (4 * a * ct) - my / (4 * a * ct) + mz / (4 * cq),
                force / (4 * ct) - mx / (4 * a * ct) - my / (4 * a * ct) - mz / (4 * cq),
                force / (4 * ct) - mx / (4 * a * ct) + my / (4 * a * ct) + mz / (4 * cq),
                force / (4 * ct) + mx / (4 * a * ct) + my / (4 * a * ct) - mz / (4 * cq),
            ]
        )
        return np.sqrt(np.clip(squared, self.rpm_min**2, self.rpm_max**2))

    def wrench_from_rpm(self, rpm: Sequence[float]) -> np.ndarray:
        return self.allocation @ (np.asarray(rpm, dtype=float) ** 2)

    def rpm_derivative(self, rpm: np.ndarray, rpm_command: np.ndarray) -> np.ndarray:
        return self.params["motor_constant"] * (rpm_command - rpm)


def euler_rate_matrix(euler: Sequence[float]) -> np.ndarray:
    phi, theta, _ = np.asarray(euler, dtype=float)
    cosine = math.cos(theta)
    if abs(cosine) < 1e-5:
        raise ValueError("ZYX Euler-angle singularity")
    return np.array(
        [
            [1.0, math.sin(phi) * math.tan(theta), math.cos(phi) * math.tan(theta)],
            [0.0, math.cos(phi), -math.sin(phi)],
            [0.0, math.sin(phi) / cosine, math.cos(phi) / cosine],
        ]
    )


def state_derivative(state: np.ndarray, rpm_command: np.ndarray, params: dict, motor: MotorModel) -> np.ndarray:
    position = state[0:3]
    velocity = state[3:6]
    euler = state[6:9]
    omega = state[9:12]
    rpm = np.clip(state[12:16], motor.rpm_min, motor.rpm_max)
    wrench = motor.wrench_from_rpm(rpm)
    rotation = rotation_matrix(euler)
    acceleration = np.array([0.0, 0.0, -params["gravity"]]) + rotation @ np.array(
        [0.0, 0.0, wrench[0] / params["mass"]]
    )
    inertia = params["inertia_matrix"]
    omega_dot = np.linalg.solve(inertia, wrench[1:4] - np.cross(omega, inertia @ omega))
    derivative = np.zeros(16, dtype=float)
    derivative[0:3] = velocity
    derivative[3:6] = acceleration
    derivative[6:9] = euler_rate_matrix(euler) @ omega
    derivative[9:12] = omega_dot
    derivative[12:16] = motor.rpm_derivative(rpm, rpm_command)
    return derivative


def rk4_step(state: np.ndarray, rpm_command: np.ndarray, dt: float, params: dict, motor: MotorModel) -> np.ndarray:
    k1 = state_derivative(state, rpm_command, params, motor)
    k2 = state_derivative(state + 0.5 * dt * k1, rpm_command, params, motor)
    k3 = state_derivative(state + 0.5 * dt * k2, rpm_command, params, motor)
    k4 = state_derivative(state + dt * k3, rpm_command, params, motor)
    result = state + dt * (k1 + 2 * k2 + 2 * k3 + k4) / 6.0
    result[12:16] = np.clip(result[12:16], motor.rpm_min, motor.rpm_max)
    return result


def simulate(
    desired: np.ndarray,
    params: dict,
    gains: dict[str, Sequence[float]],
) -> np.ndarray:
    """Run the complete closed loop and return a 15-row actual trajectory."""
    samples = desired.shape[1]
    motor = MotorModel(params)
    position_integral = make_position_integral()
    attitude_integral = make_attitude_integral()
    state = np.zeros(16, dtype=float)
    state[0:3] = desired[0:3, 0]
    state[3:6] = desired[3:6, 0]
    state[6:9] = desired[6:9, 0]
    state[12:16] = params["hover_rpm"]
    actual = np.zeros((15, samples), dtype=float)
    for k in range(samples):
        thrust, _, force_world = position_controller(
            state[:15], desired[:, k], params, position_integral, gains
        )
        target_angles = attitude_planner(force_world, desired[8, k])
        moments = attitude_controller(state[:15], target_angles, params, attitude_integral, gains)
        rpm_command = motor.wrench_to_rpm((thrust, moments[0], moments[1], moments[2]))
        acceleration = state_derivative(state, rpm_command, params, motor)[3:6]
        actual[:, k] = np.concatenate((state[:12], acceleration))
        if k + 1 < samples:
            state = rk4_step(state, rpm_command, params["dt"], params, motor)
    return actual


def stepinfo_3d(actual_position: np.ndarray, desired_position: np.ndarray, time: np.ndarray, settling_threshold: float = 0.02) -> dict[str, float]:
    """Compute distance-based 3D rise, settling, overshoot, and final error."""
    actual_position = np.asarray(actual_position, dtype=float)
    desired_position = np.asarray(desired_position, dtype=float)
    time = np.asarray(time, dtype=float)
    target = desired_position[:, -1]
    distance = np.linalg.norm(actual_position - target[:, None], axis=0)
    initial = float(distance[0])
    final_error = float(distance[-1])
    if initial <= 1e-12:
        return {"RiseTime": 0.0, "SettlingTime": 0.0, "Overshoot_pct": 0.0, "SteadyStateError": final_error}
    rise_indices = np.flatnonzero(distance <= 0.1 * initial)
    rise_time = float(time[rise_indices[0]]) if rise_indices.size else float(time[-1])
    outside = np.flatnonzero(distance > settling_threshold * initial)
    settling_time = float(time[outside[-1]]) if outside.size else 0.0
    settled_indices = np.flatnonzero(distance <= settling_threshold * initial)
    first_settled = settled_indices[0] if settled_indices.size else len(distance) - 1
    overshoot = float(np.max(distance[first_settled:]) / initial * 100.0)
    return {
        "RiseTime": rise_time,
        "SettlingTime": settling_time,
        "Overshoot_pct": overshoot,
        "SteadyStateError": final_error,
    }


def plot_quadrotor(
    state: np.ndarray,
    state_des: np.ndarray,
    time_vec: np.ndarray,
    save_dir: str | os.PathLike[str],
    params_path: str | os.PathLike[str] = PARAMETER_FILE,
) -> None:
    """Save desired/actual, instantaneous-error, and cumulative-error figures."""
    with open(params_path, encoding="utf-8") as handle:
        sample_rate = float(yaml.safe_load(handle)["sample_rate"])
    time_step = 1.0 / sample_rate
    os.makedirs(save_dir, exist_ok=True)
    labels = [
        ("Position", ("x", "y", "z")),
        ("Velocity", ("vx", "vy", "vz")),
        ("Orientation", (r"$\phi$", r"$\theta$", r"$\psi$")),
        ("Angular velocity", ("p", "q", "r")),
        ("Acceleration", ("ax", "ay", "az")),
    ]
    groups = [(0, 3), (3, 6), (6, 9), (9, 12), (12, 15)]
    error = state - state_des
    cumulative = time_step * np.cumsum(np.abs(error), axis=1)
    for filename, mode, values in (
        ("desired_vs_actual.png", "overlay", None),
        ("errors.png", "error", error),
        ("cumulative_errors.png", "cumulative", cumulative),
    ):
        fig, axes = plt.subplots(5, 3, figsize=(16, 20), squeeze=False)
        for row, ((title, axis_labels), (start, end)) in enumerate(zip(labels, groups)):
            for col in range(3):
                axis = axes[row, col]
                if mode == "overlay":
                    axis.plot(time_vec, state_des[start + col], "b", label="desired")
                    axis.plot(time_vec, state[start + col], "r", label="actual")
                    if row == 0 and col == 0:
                        axis.legend()
                else:
                    axis.plot(time_vec, values[start + col], "k")
                axis.set_title(f"{title}: {axis_labels[col]}")
                axis.set_xlabel("Time [s]")
                axis.grid(True, alpha=0.25)
        fig.tight_layout()
        fig.savefig(Path(save_dir) / filename, dpi=110)
        plt.close(fig)


def gains_for_simulation() -> dict[str, list[float]]:
    """Conservative gains tuned for the configured 200 Hz physical model."""
    return {
        "kp_pos": [15.0, 15.0, 25.0],
        "ki_pos": [0.0, 0.0, 0.0],
        "kd_pos": [8.0, 8.0, 12.0],
        "kp_att": [0.6, 0.6, 0.27],
        "ki_att": [0.0, 0.0, 0.0],
        "kd_att": [0.07, 0.07, 0.049],
    }


def write_json(path: str | os.PathLike[str], value: dict) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2)


__all__ = [
    "FlightPlan",
    "FlightPlanParser",
    "MotorModel",
    "attitude_controller",
    "attitude_planner",
    "gains_for_simulation",
    "load_params",
    "make_attitude_integral",
    "make_position_integral",
    "parse_flight_plan",
    "plot_quadrotor",
    "position_controller",
    "rotation_matrix",
    "simulate",
    "state_derivative",
    "stepinfo_3d",
    "trajectory_planner",
]
