import re
import numpy as np


_TAKEOFF_RE = re.compile(r'^\s*Take\s+off\s+to\s+([+-]?[0-9]*\.?[0-9]+)\s*m\s*height\s+in\s+([+-]?[0-9]*\.?[0-9]+)\s*seconds\s*$', re.IGNORECASE)
_HOVER_RE = re.compile(r'^\s*Hover\s+at\s+([+-]?[0-9]*\.?[0-9]+)\s*m\s*height\s+for\s+([+-]?[0-9]*\.?[0-9]+)\s*seconds\s*$', re.IGNORECASE)
_LAND_RE = re.compile(r'^\s*Land\s+from\s+([+-]?[0-9]*\.?[0-9]+)\s*m\s*height\s+in\s+([+-]?[0-9]*\.?[0-9]+)\s*seconds\s*$', re.IGNORECASE)
_FLY_RE = re.compile(
    r'^\s*Fly\s+from\s*\(\s*([+-]?[0-9]*\.?[0-9]+)\s*,\s*([+-]?[0-9]*\.?[0-9]+)\s*,\s*([+-]?[0-9]*\.?[0-9]+)\s*\)\s*'
    r'to\s*\(\s*([+-]?[0-9]*\.?[0-9]+)\s*,\s*([+-]?[0-9]*\.?[0-9]+)\s*,\s*([+-]?[0-9]*\.?[0-9]+)\s*\)\s*'
    r'in\s+([+-]?[0-9]*\.?[0-9]+)\s*seconds\s*$',
    re.IGNORECASE,
)


class FlightPlanParser:
    def __init__(self):
        self._waypoints = []  # list of [x,y,z,yaw]
        self._times = []
        self._modes = []
        self._t = 0.0

    def _ensure_start(self, waypoint):
        if not self._waypoints:
            self._waypoints.append(list(waypoint))
            self._times.append(0.0)
            self._t = 0.0

    def _append_end(self, end_wp, duration, mode):
        self._t += float(duration)
        self._waypoints.append(list(end_wp))
        self._times.append(self._t)
        self._modes.append(mode)

    def feed_line(self, line: str):
        line = line.strip()
        if not line:
            return

        m = _TAKEOFF_RE.match(line)
        if m:
            h = float(m.group(1))
            dur = float(m.group(2))
            start = [0.0, 0.0, 0.0, 0.0]
            self._ensure_start(start)
            self._append_end([0.0, 0.0, h, 0.0], dur, 'takeoff')
            return

        m = _HOVER_RE.match(line)
        if m:
            h = float(m.group(1))
            dur = float(m.group(2))
            start = [0.0, 0.0, h, 0.0]
            self._ensure_start(start)
            self._append_end([0.0, 0.0, h, 0.0], dur, 'hover')
            return

        m = _LAND_RE.match(line)
        if m:
            h = float(m.group(1))
            dur = float(m.group(2))
            start = [0.0, 0.0, h, 0.0]
            self._ensure_start(start)
            self._append_end([0.0, 0.0, 0.0, 0.0], dur, 'land')
            return

        m = _FLY_RE.match(line)
        if m:
            x0, y0, z0, x1, y1, z1, dur = map(float, m.groups())
            start = [x0, y0, z0, 0.0]
            self._ensure_start(start)
            self._append_end([x1, y1, z1, 0.0], dur, 'fly')
            return

        raise ValueError(f'Unsupported command line: {line!r}')

    def build(self):
        waypoints = np.array(self._waypoints, dtype=float).T  # (4,n)
        times = np.array(self._times, dtype=float)
        return waypoints, times, list(self._modes)


def parse_flight_plan(text: str):
    parser = FlightPlanParser()
    for line in text.splitlines():
        parser.feed_line(line)
    return parser.build()
