import re
from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np


@dataclass
class _ParserState:
    pos: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    yaw: float = 0.0
    t: float = 0.0
    waypoints: List[List[float]] = field(default_factory=list)  # [x,y,z,yaw]
    waypoint_times: List[float] = field(default_factory=list)
    modes: List[str] = field(default_factory=list)

    def _ensure_start(self) -> None:
        if not self.waypoints:
            self.waypoints.append([*self.pos, self.yaw])
            self.waypoint_times.append(self.t)

    def handle_takeoff(self, height: float, duration: float) -> None:
        self._ensure_start()
        self.t += float(duration)
        self.pos = [self.pos[0], self.pos[1], float(height)]
        self.waypoints.append([*self.pos, self.yaw])
        self.waypoint_times.append(self.t)
        self.modes.append('takeoff')

    def handle_hover(self, height: float, duration: float) -> None:
        self._ensure_start()
        self.t += float(duration)
        self.pos = [self.pos[0], self.pos[1], float(height)]
        self.waypoints.append([*self.pos, self.yaw])
        self.waypoint_times.append(self.t)
        self.modes.append('hover')

    def handle_land(self, height: float, duration: float) -> None:
        self._ensure_start()
        self.t += float(duration)
        self.pos = [self.pos[0], self.pos[1], 0.0]
        self.waypoints.append([*self.pos, self.yaw])
        self.waypoint_times.append(self.t)
        self.modes.append('land')

    def handle_fly(
        self,
        start_xyz: Tuple[float, float, float],
        end_xyz: Tuple[float, float, float],
        duration: float,
    ) -> None:
        self._ensure_start()
        # Override start if command explicitly states it.
        self.pos = [float(start_xyz[0]), float(start_xyz[1]), float(start_xyz[2])]
        self.waypoints[-1] = [*self.pos, self.yaw]
        self.t += float(duration)
        self.pos = [float(end_xyz[0]), float(end_xyz[1]), float(end_xyz[2])]
        self.waypoints.append([*self.pos, self.yaw])
        self.waypoint_times.append(self.t)
        self.modes.append('fly')


_PAT_TAKEOFF = re.compile(
    r'^\s*Take\s+off\s+to\s+([\d\.\-]+)\s*m\s+height\s+in\s+([\d\.\-]+)\s*seconds\s*$',
    re.IGNORECASE,
)
_PAT_HOVER = re.compile(
    r'^\s*Hover\s+at\s+([\d\.\-]+)\s*m\s+height\s+for\s+([\d\.\-]+)\s*seconds\s*$',
    re.IGNORECASE,
)
_PAT_LAND = re.compile(
    r'^\s*Land\s+from\s+([\d\.\-]+)\s*m\s+height\s+in\s+([\d\.\-]+)\s*seconds\s*$',
    re.IGNORECASE,
)
_PAT_FLY = re.compile(
    r'^\s*Fly\s+from\s*\(\s*([\d\.\-]+)\s*,\s*([\d\.\-]+)\s*,\s*([\d\.\-]+)\s*\)\s*'
    r'to\s*\(\s*([\d\.\-]+)\s*,\s*([\d\.\-]+)\s*,\s*([\d\.\-]+)\s*\)\s*'
    r'in\s+([\d\.\-]+)\s*seconds\s*$',
    re.IGNORECASE,
)


def parse_flight_plan(text: str):
    """Parse natural language flight plan into waypoints, times, and modes."""

    st = _ParserState()
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue

        m = _PAT_TAKEOFF.match(line)
        if m:
            st.handle_takeoff(float(m.group(1)), float(m.group(2)))
            continue

        m = _PAT_HOVER.match(line)
        if m:
            st.handle_hover(float(m.group(1)), float(m.group(2)))
            continue

        m = _PAT_LAND.match(line)
        if m:
            st.handle_land(float(m.group(1)), float(m.group(2)))
            continue

        m = _PAT_FLY.match(line)
        if m:
            start = (float(m.group(1)), float(m.group(2)), float(m.group(3)))
            end = (float(m.group(4)), float(m.group(5)), float(m.group(6)))
            st.handle_fly(start, end, float(m.group(7)))
            continue

        raise ValueError(f'Unsupported command line: {line!r}')

    waypoints = np.asarray(st.waypoints, dtype=float).T  # (4, n)
    waypoint_times = np.asarray(st.waypoint_times, dtype=float)
    modes = list(st.modes)
    return waypoints, waypoint_times, modes
