import re
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np


_PAT_TAKEOFF = re.compile(
    r"^\s*take\s+off\s+to\s+([0-9]*\.?[0-9]+)\s*m\s*height\s*in\s*([0-9]*\.?[0-9]+)\s*seconds\s*$",
    re.IGNORECASE,
)
_PAT_HOVER = re.compile(
    r"^\s*hover\s+at\s+([0-9]*\.?[0-9]+)\s*m\s*height\s*for\s*([0-9]*\.?[0-9]+)\s*seconds\s*$",
    re.IGNORECASE,
)
_PAT_LAND = re.compile(
    r"^\s*land\s+from\s+([0-9]*\.?[0-9]+)\s*m\s*height\s*in\s*([0-9]*\.?[0-9]+)\s*seconds\s*$",
    re.IGNORECASE,
)
_PAT_FLY = re.compile(
    r"^\s*fly\s+from\s*\(\s*([+-]?[0-9]*\.?[0-9]+)\s*,\s*([+-]?[0-9]*\.?[0-9]+)\s*,\s*([+-]?[0-9]*\.?[0-9]+)\s*\)\s*"
    r"to\s*\(\s*([+-]?[0-9]*\.?[0-9]+)\s*,\s*([+-]?[0-9]*\.?[0-9]+)\s*,\s*([+-]?[0-9]*\.?[0-9]+)\s*\)\s*"
    r"in\s*([0-9]*\.?[0-9]+)\s*seconds\s*$",
    re.IGNORECASE,
)


@dataclass
class FlightPlan:
    waypoints: np.ndarray  # (4, n) rows [x,y,z,yaw]
    waypoint_times: np.ndarray  # (n,)
    modes: List[str]  # (n-1)


class FlightPlanParser:
    def __init__(self):
        self._t = 0.0
        self._pos = [0.0, 0.0, 0.0]
        self._yaw = 0.0
        self._wps: List[List[float]] = []
        self._times: List[float] = []
        self._modes: List[str] = []

    def _ensure_start(self, pos_xyz: Tuple[float, float, float]):
        if self._wps:
            return
        self._pos = [float(pos_xyz[0]), float(pos_xyz[1]), float(pos_xyz[2])]
        self._wps.append([*self._pos, self._yaw])
        self._times.append(self._t)

    def handle_line(self, line: str):
        line = line.strip()
        if not line:
            return

        m = _PAT_TAKEOFF.match(line)
        if m:
            h, dur = map(float, m.groups())
            self._ensure_start((0.0, 0.0, 0.0))
            self._t += dur
            self._pos = [self._pos[0], self._pos[1], h]
            self._wps.append([*self._pos, self._yaw])
            self._times.append(self._t)
            self._modes.append("takeoff")
            return

        m = _PAT_HOVER.match(line)
        if m:
            h, dur = map(float, m.groups())
            self._ensure_start((0.0, 0.0, h))
            self._t += dur
            self._pos = [self._pos[0], self._pos[1], h]
            self._wps.append([*self._pos, self._yaw])
            self._times.append(self._t)
            self._modes.append("hover")
            return

        m = _PAT_LAND.match(line)
        if m:
            h, dur = map(float, m.groups())
            self._ensure_start((0.0, 0.0, h))
            self._t += dur
            self._pos = [self._pos[0], self._pos[1], 0.0]
            self._wps.append([*self._pos, self._yaw])
            self._times.append(self._t)
            self._modes.append("land")
            return

        m = _PAT_FLY.match(line)
        if m:
            x0, y0, z0, x1, y1, z1, dur = map(float, m.groups())
            if not self._wps:
                self._ensure_start((x0, y0, z0))
            else:
                # If this flight plan is multi-line, we accept the provided start,
                # but do not insert an extra waypoint.
                self._pos = [x0, y0, z0]
            self._t += float(dur)
            self._pos = [x1, y1, z1]
            self._wps.append([*self._pos, self._yaw])
            self._times.append(self._t)
            self._modes.append("fly")
            return

        raise ValueError(f"Unrecognised command line: {line!r}")

    def build(self) -> FlightPlan:
        if not self._wps:
            self._ensure_start((0.0, 0.0, 0.0))

        waypoints = np.array(self._wps, dtype=float).T
        waypoint_times = np.array(self._times, dtype=float)
        return FlightPlan(waypoints=waypoints, waypoint_times=waypoint_times, modes=list(self._modes))


def parse_flight_plan(text: str):
    """Parse one or more natural-language flight plan lines.

    Returns:
        waypoints: (4, n) array rows [x,y,z,yaw]
        waypoint_times: (n,) arrival times in seconds
        modes: list of (n-1) segment mode strings
    """

    parser = FlightPlanParser()
    for line in text.splitlines():
        parser.handle_line(line)
    plan = parser.build()
    return plan.waypoints, plan.waypoint_times, plan.modes
