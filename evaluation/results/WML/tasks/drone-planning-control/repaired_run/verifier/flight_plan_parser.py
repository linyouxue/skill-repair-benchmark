import re
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np


@dataclass
class FlightPlan:
    waypoints: np.ndarray  # (4, n): x,y,z,yaw
    waypoint_times: np.ndarray  # (n,)
    modes: List[str]  # (n-1)


_TAKEOFF_RE = re.compile(
    r"^\s*Take\s*off\s*to\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*m\s*height\s*in\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*seconds\s*$",
    re.IGNORECASE,
)

_HOVER_RE = re.compile(
    r"^\s*Hover\s*at\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*m\s*height\s*for\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*seconds\s*$",
    re.IGNORECASE,
)

_LAND_RE = re.compile(
    r"^\s*Land\s*from\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*m\s*height\s*in\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*seconds\s*$",
    re.IGNORECASE,
)

_FLY_RE = re.compile(
    r"^\s*Fly\s*from\s*\(\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*,\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*,\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*\)\s*"
    r"to\s*\(\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*,\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*,\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*\)\s*"
    r"in\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*seconds\s*$",
    re.IGNORECASE,
)


class _Parser:
    def __init__(self):
        self._t = 0.0
        self._pos = np.array([0.0, 0.0, 0.0], dtype=float)
        self._yaw = 0.0
        self._wps: List[np.ndarray] = []
        self._times: List[float] = []
        self._modes: List[str] = []

    def _ensure_start(self, start_pos: np.ndarray):
        if not self._wps:
            self._pos = start_pos.copy()
            self._wps.append(np.array([*self._pos, self._yaw], dtype=float))
            self._times.append(self._t)

    def handle_line(self, line: str):
        line = line.strip()
        if not line:
            return

        m = _TAKEOFF_RE.match(line)
        if m:
            h = float(m.group(1))
            dur = float(m.group(2))
            self._ensure_start(np.array([0.0, 0.0, 0.0], dtype=float))
            self._t += dur
            self._pos[2] = h
            self._wps.append(np.array([*self._pos, self._yaw], dtype=float))
            self._times.append(self._t)
            self._modes.append("takeoff")
            return

        m = _HOVER_RE.match(line)
        if m:
            h = float(m.group(1))
            dur = float(m.group(2))
            # If hover is the first instruction, we start already at altitude h.
            self._ensure_start(np.array([0.0, 0.0, h], dtype=float))
            self._pos[2] = h
            self._t += dur
            self._wps.append(np.array([*self._pos, self._yaw], dtype=float))
            self._times.append(self._t)
            self._modes.append("hover")
            return

        m = _LAND_RE.match(line)
        if m:
            h = float(m.group(1))
            dur = float(m.group(2))
            self._ensure_start(np.array([0.0, 0.0, h], dtype=float))
            self._pos[2] = h
            self._t += dur
            self._pos[2] = 0.0
            self._wps.append(np.array([*self._pos, self._yaw], dtype=float))
            self._times.append(self._t)
            self._modes.append("land")
            return

        m = _FLY_RE.match(line)
        if m:
            x0, y0, z0, x1, y1, z1, dur = map(float, m.groups())
            start = np.array([x0, y0, z0], dtype=float)
            end = np.array([x1, y1, z1], dtype=float)
            self._ensure_start(start)
            # If the plan already started but doesn't match the stated start, jump.
            if np.linalg.norm(self._pos - start) > 1e-9:
                self._pos = start.copy()
                self._wps.append(np.array([*self._pos, self._yaw], dtype=float))
                self._times.append(self._t)
            self._t += dur
            self._pos = end
            self._wps.append(np.array([*self._pos, self._yaw], dtype=float))
            self._times.append(self._t)
            self._modes.append("fly")
            return

        raise ValueError(f"Unrecognized command line: {line!r}")

    def build(self) -> FlightPlan:
        if not self._wps:
            raise ValueError("Empty flight plan")
        waypoints = np.stack(self._wps, axis=1)  # (4, n)
        waypoint_times = np.array(self._times, dtype=float)
        return FlightPlan(waypoints=waypoints, waypoint_times=waypoint_times, modes=self._modes)


def parse_flight_plan(text: str) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """Parse natural language commands into waypoints, times, and segment modes."""
    p = _Parser()
    for line in text.splitlines():
        p.handle_line(line)
    fp = p.build()
    return fp.waypoints, fp.waypoint_times, fp.modes
