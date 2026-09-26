from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np


_TAKEOFF_RE = re.compile(
    r"^\s*take\s+off\s+to\s+([0-9]*\.?[0-9]+)\s*m\s*height\s*in\s*([0-9]*\.?[0-9]+)\s*seconds\s*$",
    re.IGNORECASE,
)
_HOVER_RE = re.compile(
    r"^\s*hover\s+at\s+([0-9]*\.?[0-9]+)\s*m\s*height\s*for\s*([0-9]*\.?[0-9]+)\s*seconds\s*$",
    re.IGNORECASE,
)
_LAND_RE = re.compile(
    r"^\s*land\s+from\s+([0-9]*\.?[0-9]+)\s*m\s*height\s*in\s*([0-9]*\.?[0-9]+)\s*seconds\s*$",
    re.IGNORECASE,
)
_FLY_RE = re.compile(
    r"^\s*fly\s+from\s*\(\s*([+-]?[0-9]*\.?[0-9]+)\s*,\s*([+-]?[0-9]*\.?[0-9]+)\s*,\s*([+-]?[0-9]*\.?[0-9]+)\s*\)\s*"
    r"to\s*\(\s*([+-]?[0-9]*\.?[0-9]+)\s*,\s*([+-]?[0-9]*\.?[0-9]+)\s*,\s*([+-]?[0-9]*\.?[0-9]+)\s*\)\s*"
    r"in\s*([0-9]*\.?[0-9]+)\s*seconds\s*$",
    re.IGNORECASE,
)


@dataclass
class _Parser:
    pos: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    yaw: float = 0.0
    t: float = 0.0
    waypoints: list[list[float]] = field(default_factory=list)  # [x,y,z,yaw]
    times: list[float] = field(default_factory=list)
    modes: list[str] = field(default_factory=list)

    def _push_start_if_needed(self) -> None:
        if not self.waypoints:
            self.waypoints.append(self.pos.copy() + [self.yaw])
            self.times.append(0.0)

    def handle(self, line: str) -> None:
        line = line.strip()
        if not line:
            return

        m = _TAKEOFF_RE.match(line)
        if m:
            h = float(m.group(1))
            dt = float(m.group(2))
            self.pos = [0.0, 0.0, 0.0]
            self.t = 0.0
            self._push_start_if_needed()
            self.t += dt
            self.pos[2] = h
            self.waypoints.append(self.pos.copy() + [self.yaw])
            self.times.append(self.t)
            self.modes.append('takeoff')
            return

        m = _HOVER_RE.match(line)
        if m:
            h = float(m.group(1))
            dt = float(m.group(2))
            self.pos = [0.0, 0.0, h]
            self.t = 0.0
            self._push_start_if_needed()
            self.t += dt
            self.waypoints.append(self.pos.copy() + [self.yaw])
            self.times.append(self.t)
            self.modes.append('hover')
            return

        m = _LAND_RE.match(line)
        if m:
            h = float(m.group(1))
            dt = float(m.group(2))
            self.pos = [0.0, 0.0, h]
            self.t = 0.0
            self._push_start_if_needed()
            self.t += dt
            self.pos[2] = 0.0
            self.waypoints.append(self.pos.copy() + [self.yaw])
            self.times.append(self.t)
            self.modes.append('land')
            return

        m = _FLY_RE.match(line)
        if m:
            x0, y0, z0 = float(m.group(1)), float(m.group(2)), float(m.group(3))
            x1, y1, z1 = float(m.group(4)), float(m.group(5)), float(m.group(6))
            dt = float(m.group(7))
            self.pos = [x0, y0, z0]
            self.t = 0.0
            self._push_start_if_needed()
            self.t += dt
            self.pos = [x1, y1, z1]
            self.waypoints.append(self.pos.copy() + [self.yaw])
            self.times.append(self.t)
            self.modes.append('fly')
            return

        raise ValueError(f'Unsupported command line: {line!r}')


def parse_flight_plan(text: str):
    parser = _Parser()
    for line in text.splitlines():
        parser.handle(line)

    waypoints = np.asarray(parser.waypoints, dtype=float).T  # (4, n)
    waypoint_times = np.asarray(parser.times, dtype=float)
    return waypoints, waypoint_times, list(parser.modes)
