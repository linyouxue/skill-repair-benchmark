from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np


_takeoff_re = re.compile(r"^\s*take\s*off\s*to\s*([0-9]*\.?[0-9]+)\s*m\s*height\s*in\s*([0-9]*\.?[0-9]+)\s*seconds\s*$", re.IGNORECASE)
_hover_re = re.compile(r"^\s*hover\s*at\s*([0-9]*\.?[0-9]+)\s*m\s*height\s*for\s*([0-9]*\.?[0-9]+)\s*seconds\s*$", re.IGNORECASE)
_land_re = re.compile(r"^\s*land\s*from\s*([0-9]*\.?[0-9]+)\s*m\s*height\s*in\s*([0-9]*\.?[0-9]+)\s*seconds\s*$", re.IGNORECASE)
_fly_re = re.compile(
    r"^\s*fly\s*from\s*\(\s*([+-]?[0-9]*\.?[0-9]+)\s*,\s*([+-]?[0-9]*\.?[0-9]+)\s*,\s*([+-]?[0-9]*\.?[0-9]+)\s*\)\s*"
    r"to\s*\(\s*([+-]?[0-9]*\.?[0-9]+)\s*,\s*([+-]?[0-9]*\.?[0-9]+)\s*,\s*([+-]?[0-9]*\.?[0-9]+)\s*\)\s*"
    r"in\s*([0-9]*\.?[0-9]+)\s*seconds\s*$",
    re.IGNORECASE,
)


@dataclass
class ParsedPlan:
    waypoints: np.ndarray  # (4, n) rows: x, y, z, yaw
    waypoint_times: np.ndarray  # (n,)
    modes: List[str]  # (n-1)


class FlightPlanParser:
    def __init__(self) -> None:
        self._pos = np.zeros(3, dtype=float)
        self._yaw = 0.0
        self._t = 0.0
        self._wps: List[np.ndarray] = []
        self._times: List[float] = []
        self._modes: List[str] = []

    def _ensure_start(self, start_pos: np.ndarray) -> None:
        if self._wps:
            return
        self._pos = start_pos.astype(float).copy()
        self._t = 0.0
        self._wps.append(np.array([self._pos[0], self._pos[1], self._pos[2], self._yaw], dtype=float))
        self._times.append(self._t)

    def feed_line(self, line: str) -> None:
        line = line.strip()
        if not line:
            return

        m = _takeoff_re.match(line)
        if m:
            h = float(m.group(1))
            dur = float(m.group(2))
            self._ensure_start(np.array([0.0, 0.0, 0.0]))
            self._t += dur
            self._pos = np.array([0.0, 0.0, h], dtype=float)
            self._wps.append(np.array([self._pos[0], self._pos[1], self._pos[2], self._yaw], dtype=float))
            self._times.append(self._t)
            self._modes.append("takeoff")
            return

        m = _hover_re.match(line)
        if m:
            h = float(m.group(1))
            dur = float(m.group(2))
            self._ensure_start(np.array([0.0, 0.0, h]))
            self._t += dur
            self._pos = np.array([0.0, 0.0, h], dtype=float)
            self._wps.append(np.array([self._pos[0], self._pos[1], self._pos[2], self._yaw], dtype=float))
            self._times.append(self._t)
            self._modes.append("hover")
            return

        m = _land_re.match(line)
        if m:
            h = float(m.group(1))
            dur = float(m.group(2))
            self._ensure_start(np.array([0.0, 0.0, h]))
            self._t += dur
            self._pos = np.array([0.0, 0.0, 0.0], dtype=float)
            self._wps.append(np.array([self._pos[0], self._pos[1], self._pos[2], self._yaw], dtype=float))
            self._times.append(self._t)
            self._modes.append("land")
            return

        m = _fly_re.match(line)
        if m:
            x0, y0, z0 = float(m.group(1)), float(m.group(2)), float(m.group(3))
            x1, y1, z1 = float(m.group(4)), float(m.group(5)), float(m.group(6))
            dur = float(m.group(7))
            self._ensure_start(np.array([x0, y0, z0], dtype=float))
            self._t += dur
            self._pos = np.array([x1, y1, z1], dtype=float)
            self._wps.append(np.array([self._pos[0], self._pos[1], self._pos[2], self._yaw], dtype=float))
            self._times.append(self._t)
            self._modes.append("fly")
            return

        raise ValueError(f"Unsupported command line: {line!r}")

    def finalize(self) -> ParsedPlan:
        waypoints = np.stack(self._wps, axis=1)  # (4, n)
        waypoint_times = np.array(self._times, dtype=float)
        return ParsedPlan(waypoints=waypoints, waypoint_times=waypoint_times, modes=list(self._modes))


def parse_flight_plan(text: str) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    parser = FlightPlanParser()
    for line in text.splitlines():
        parser.feed_line(line)
    plan = parser.finalize()
    return plan.waypoints, plan.waypoint_times, plan.modes
