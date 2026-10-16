"""Parse natural-language flight-plan commands into waypoint arrays."""

import re
import numpy as np


_RE_TAKEOFF = re.compile(
    r'take\s*off\s+to\s+([-\d.]+)\s*m\s+height\s+in\s+([-\d.]+)\s*seconds?',
    re.IGNORECASE,
)
_RE_HOVER = re.compile(
    r'hover\s+at\s+([-\d.]+)\s*m\s+height\s+for\s+([-\d.]+)\s*seconds?',
    re.IGNORECASE,
)
_RE_LAND = re.compile(
    r'land\s+from\s+([-\d.]+)\s*m\s+height\s+in\s+([-\d.]+)\s*seconds?',
    re.IGNORECASE,
)
_RE_FLY = re.compile(
    r'fly\s+from\s*\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)\s*'
    r'to\s*\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)\s*'
    r'in\s+([-\d.]+)\s*seconds?',
    re.IGNORECASE,
)


class FlightPlanParser:
    def __init__(self):
        self.position = [0.0, 0.0, 0.0, 0.0]  # x, y, z, yaw
        self.time = 0.0
        self.waypoints = []
        self.times = []
        self.modes = []

    def _ensure_start(self, initial_position=None):
        if not self.waypoints:
            if initial_position is not None:
                self.position = list(initial_position) + [0.0] * (4 - len(initial_position))
            self.waypoints.append(list(self.position))
            self.times.append(0.0)

    def _push(self, mode, duration):
        self.time += duration
        self.waypoints.append(list(self.position))
        self.times.append(self.time)
        self.modes.append(mode)

    def handle(self, line):
        line = line.strip()
        if not line:
            return

        m = _RE_TAKEOFF.search(line)
        if m:
            h, t = float(m.group(1)), float(m.group(2))
            self._ensure_start([0.0, 0.0, 0.0])
            self.position[2] = h
            self._push('takeoff', t)
            return

        m = _RE_HOVER.search(line)
        if m:
            h, t = float(m.group(1)), float(m.group(2))
            self._ensure_start([0.0, 0.0, h])
            self.position[2] = h
            self._push('hover', t)
            return

        m = _RE_LAND.search(line)
        if m:
            h, t = float(m.group(1)), float(m.group(2))
            self._ensure_start([0.0, 0.0, h])
            self.position[2] = 0.0
            self._push('land', t)
            return

        m = _RE_FLY.search(line)
        if m:
            x0, y0, z0, x1, y1, z1, t = (float(m.group(i)) for i in range(1, 8))
            self._ensure_start([x0, y0, z0])
            self.position[0:3] = [x1, y1, z1]
            self._push('fly', t)
            return

        raise ValueError(f'Unrecognised command: {line!r}')

    def result(self):
        wp = np.array(self.waypoints, dtype=float).T  # (4, n)
        times = np.array(self.times, dtype=float)
        return wp, times, list(self.modes)


def parse_flight_plan(text):
    parser = FlightPlanParser()
    for line in text.splitlines():
        if line.strip():
            parser.handle(line)
    return parser.result()
