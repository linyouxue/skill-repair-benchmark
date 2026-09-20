import re
import numpy as np


class FlightPlanParser:
    def __init__(self):
        self.pos = [0.0, 0.0, 0.0]  # current x, y, z
        self.yaw = 0.0
        self.t = 0.0
        self.waypoints = []      # each entry [x, y, z, yaw]
        self.times = []          # arrival time of each waypoint
        self.modes = []          # segment mode strings

        num = r'([-+]?\d*\.?\d+)'
        self.re_takeoff = re.compile(rf'take\s*off\s*to\s*{num}\s*m?\s*height\s*in\s*{num}\s*seconds?', re.IGNORECASE)
        self.re_hover   = re.compile(rf'hover\s*at\s*{num}\s*m?\s*height\s*for\s*{num}\s*seconds?', re.IGNORECASE)
        self.re_land    = re.compile(rf'land\s*from\s*{num}\s*m?\s*height\s*in\s*{num}\s*seconds?', re.IGNORECASE)
        self.re_fly     = re.compile(
            rf'fly\s*from\s*\(\s*{num}\s*,\s*{num}\s*,\s*{num}\s*\)\s*to\s*'
            rf'\(\s*{num}\s*,\s*{num}\s*,\s*{num}\s*\)\s*in\s*{num}\s*seconds?',
            re.IGNORECASE)

    def _ensure_start(self):
        if not self.waypoints:
            self.waypoints.append(self.pos + [self.yaw])
            self.times.append(self.t)

    def feed(self, line):
        line = line.strip()
        if not line:
            return

        m = self.re_takeoff.search(line)
        if m:
            h, dur = float(m.group(1)), float(m.group(2))
            self._ensure_start()
            self.pos[2] = h
            self.t += dur
            self.waypoints.append(self.pos.copy() + [self.yaw])
            self.times.append(self.t)
            self.modes.append('takeoff')
            return

        m = self.re_hover.search(line)
        if m:
            h, dur = float(m.group(1)), float(m.group(2))
            self.pos[2] = h  # if we're not already there, assume we are
            self._ensure_start()
            self.t += dur
            self.waypoints.append(self.pos.copy() + [self.yaw])
            self.times.append(self.t)
            self.modes.append('hover')
            return

        m = self.re_land.search(line)
        if m:
            h, dur = float(m.group(1)), float(m.group(2))
            self.pos[2] = h
            self._ensure_start()
            self.pos[2] = 0.0
            self.t += dur
            self.waypoints.append(self.pos.copy() + [self.yaw])
            self.times.append(self.t)
            self.modes.append('land')
            return

        m = self.re_fly.search(line)
        if m:
            xs, ys, zs = float(m.group(1)), float(m.group(2)), float(m.group(3))
            xe, ye, ze = float(m.group(4)), float(m.group(5)), float(m.group(6))
            dur = float(m.group(7))
            self.pos = [xs, ys, zs]
            self._ensure_start()
            self.pos = [xe, ye, ze]
            self.t += dur
            self.waypoints.append(self.pos.copy() + [self.yaw])
            self.times.append(self.t)
            self.modes.append('fly')
            return

        raise ValueError(f'Unrecognised command: {line}')

    def result(self):
        wp = np.array(self.waypoints, dtype=float).T  # shape (4, n)
        t  = np.array(self.times, dtype=float)
        return wp, t, list(self.modes)


def parse_flight_plan(text):
    parser = FlightPlanParser()
    for line in text.splitlines():
        if line.strip():
            parser.feed(line)
    return parser.result()
