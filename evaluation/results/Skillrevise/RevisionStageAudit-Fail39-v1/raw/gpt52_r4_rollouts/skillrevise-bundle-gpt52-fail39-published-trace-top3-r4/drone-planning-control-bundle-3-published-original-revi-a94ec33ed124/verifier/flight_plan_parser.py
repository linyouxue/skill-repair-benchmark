import re
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np


@dataclass
class ParsedPlan:
    waypoints: np.ndarray  # (4, n) rows: x,y,z,yaw
    waypoint_times: np.ndarray  # (n,)
    modes: List[str]  # (n-1)


class FlightPlanParser:
    def __init__(self):
        self._pos = [0.0, 0.0, 0.0]
        self._yaw = 0.0
        self._t = 0.0
        self._wps: List[List[float]] = []
        self._times: List[float] = []
        self._modes: List[str] = []

        self._re_takeoff = re.compile(r"^\s*take\s+off\s+to\s+([+-]?(?:\d+\.?\d*|\d*\.?\d+))\s*m\s*height\s*in\s*([+-]?(?:\d+\.?\d*|\d*\.?\d+))\s*seconds\s*$",
                                     re.IGNORECASE)
        self._re_hover = re.compile(r"^\s*hover\s+at\s+([+-]?(?:\d+\.?\d*|\d*\.?\d+))\s*m\s*height\s*for\s*([+-]?(?:\d+\.?\d*|\d*\.?\d+))\s*seconds\s*$",
                                   re.IGNORECASE)
        self._re_land = re.compile(r"^\s*land\s+from\s+([+-]?(?:\d+\.?\d*|\d*\.?\d+))\s*m\s*height\s*in\s*([+-]?(?:\d+\.?\d*|\d*\.?\d+))\s*seconds\s*$",
                                  re.IGNORECASE)
        self._re_fly = re.compile(
            r"^\s*fly\s+from\s*\(\s*([+-]?(?:\d+\.?\d*|\d*\.?\d+))\s*,\s*([+-]?(?:\d+\.?\d*|\d*\.?\d+))\s*,\s*([+-]?(?:\d+\.?\d*|\d*\.?\d+))\s*\)\s*"
            r"to\s*\(\s*([+-]?(?:\d+\.?\d*|\d*\.?\d+))\s*,\s*([+-]?(?:\d+\.?\d*|\d*\.?\d+))\s*,\s*([+-]?(?:\d+\.?\d*|\d*\.?\d+))\s*\)\s*"
            r"in\s*([+-]?(?:\d+\.?\d*|\d*\.?\d+))\s*seconds\s*$",
            re.IGNORECASE,
        )

    def _ensure_start(self):
        if not self._wps:
            self._wps.append([*self._pos, self._yaw])
            self._times.append(0.0)

    def parse_line(self, line: str) -> None:
        line = line.strip()
        if not line:
            return

        m = self._re_takeoff.match(line)
        if m:
            self._ensure_start()
            h = float(m.group(1))
            dt = float(m.group(2))
            self._t += dt
            self._pos[2] = h
            self._wps.append([*self._pos, self._yaw])
            self._times.append(self._t)
            self._modes.append("takeoff")
            return

        m = self._re_hover.match(line)
        if m:
            h = float(m.group(1))
            dt = float(m.group(2))
            if not self._wps:
                self._pos[2] = h
            self._ensure_start()
            self._pos[2] = h
            self._t += dt
            self._wps.append([*self._pos, self._yaw])
            self._times.append(self._t)
            self._modes.append("hover")
            return

        m = self._re_land.match(line)
        if m:
            h = float(m.group(1))
            dt = float(m.group(2))
            if not self._wps:
                self._pos[2] = h
            self._ensure_start()
            self._pos[2] = h
            self._t += dt
            self._pos[2] = 0.0
            self._wps.append([*self._pos, self._yaw])
            self._times.append(self._t)
            self._modes.append("land")
            return

        m = self._re_fly.match(line)
        if m:
            self._ensure_start()
            x0, y0, z0 = float(m.group(1)), float(m.group(2)), float(m.group(3))
            x1, y1, z1 = float(m.group(4)), float(m.group(5)), float(m.group(6))
            dt = float(m.group(7))
            if not self._wps or self._times[-1] == 0.0:
                self._pos = [x0, y0, z0]
                if self._wps:
                    self._wps[-1] = [*self._pos, self._yaw]
                else:
                    self._wps.append([*self._pos, self._yaw])
                    self._times.append(0.0)
            self._t += dt
            self._pos = [x1, y1, z1]
            self._wps.append([*self._pos, self._yaw])
            self._times.append(self._t)
            self._modes.append("fly")
            return

        raise ValueError(f"Unrecognized command line: {line}")

    def finalize(self) -> ParsedPlan:
        waypoints = np.array(self._wps, dtype=float).T
        waypoint_times = np.array(self._times, dtype=float)
        return ParsedPlan(waypoints=waypoints, waypoint_times=waypoint_times, modes=list(self._modes))


def parse_flight_plan(text: str) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    parser = FlightPlanParser()
    for line in text.splitlines():
        parser.parse_line(line)
    plan = parser.finalize()
    return plan.waypoints, plan.waypoint_times, plan.modes
