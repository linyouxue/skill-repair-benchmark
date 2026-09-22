import re
from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np


_TAKEOFF_RE = re.compile(
    r"^Take\s*off\s*to\s*([0-9]*\.?[0-9]+)\s*m\s*height\s*in\s*([0-9]*\.?[0-9]+)\s*seconds\s*$",
    re.IGNORECASE,
)
_HOVER_RE = re.compile(
    r"^Hover\s*at\s*([0-9]*\.?[0-9]+)\s*m\s*height\s*for\s*([0-9]*\.?[0-9]+)\s*seconds\s*$",
    re.IGNORECASE,
)
_LAND_RE = re.compile(
    r"^Land\s*from\s*([0-9]*\.?[0-9]+)\s*m\s*height\s*in\s*([0-9]*\.?[0-9]+)\s*seconds\s*$",
    re.IGNORECASE,
)
_FLY_RE = re.compile(
    r"^Fly\s*from\s*\(\s*([0-9\-]*\.?[0-9]+)\s*,\s*([0-9\-]*\.?[0-9]+)\s*,\s*([0-9\-]*\.?[0-9]+)\s*\)\s*"
    r"to\s*\(\s*([0-9\-]*\.?[0-9]+)\s*,\s*([0-9\-]*\.?[0-9]+)\s*,\s*([0-9\-]*\.?[0-9]+)\s*\)\s*"
    r"in\s*([0-9]*\.?[0-9]+)\s*seconds\s*$",
    re.IGNORECASE,
)


@dataclass
class FlightPlanParser:
    current_pos: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])  # x,y,z,yaw
    current_time: float = 0.0
    waypoints: List[List[float]] = field(default_factory=list)
    waypoint_times: List[float] = field(default_factory=list)
    modes: List[str] = field(default_factory=list)

    def _ensure_start(self, pos: List[float]) -> None:
        if not self.waypoints:
            self.current_pos = list(pos)
            self.waypoints.append(list(pos))
            self.waypoint_times.append(0.0)
            self.current_time = 0.0

    def _append_end(self, end_pos: List[float], dt: float, mode: str) -> None:
        self.current_time += float(dt)
        self.current_pos = list(end_pos)
        self.waypoints.append(list(end_pos))
        self.waypoint_times.append(float(self.current_time))
        self.modes.append(mode)

    def add_line(self, line: str) -> None:
        line = line.strip()
        if not line:
            return

        m = _TAKEOFF_RE.match(line)
        if m:
            h = float(m.group(1))
            duration = float(m.group(2))
            self._ensure_start([0.0, 0.0, 0.0, 0.0])
            self._append_end([0.0, 0.0, h, 0.0], duration, "takeoff")
            return

        m = _HOVER_RE.match(line)
        if m:
            h = float(m.group(1))
            duration = float(m.group(2))
            self._ensure_start([0.0, 0.0, h, 0.0])
            self._append_end(list(self.current_pos), duration, "hover")
            return

        m = _LAND_RE.match(line)
        if m:
            h = float(m.group(1))
            duration = float(m.group(2))
            self._ensure_start([0.0, 0.0, h, 0.0])
            self._append_end([self.current_pos[0], self.current_pos[1], 0.0, self.current_pos[3]], duration, "land")
            return

        m = _FLY_RE.match(line)
        if m:
            x0, y0, z0 = float(m.group(1)), float(m.group(2)), float(m.group(3))
            x1, y1, z1 = float(m.group(4)), float(m.group(5)), float(m.group(6))
            duration = float(m.group(7))
            if not self.waypoints:
                self._ensure_start([x0, y0, z0, 0.0])
            self._append_end([x1, y1, z1, 0.0], duration, "fly")
            return

        raise ValueError(f"Unsupported command line: {line!r}")


def parse_flight_plan(text: str) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    parser = FlightPlanParser()
    for line in text.splitlines():
        parser.add_line(line)

    waypoints = np.array(parser.waypoints, dtype=float).T
    waypoint_times = np.array(parser.waypoint_times, dtype=float)
    return waypoints, waypoint_times, list(parser.modes)
