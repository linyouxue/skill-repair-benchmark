from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np


_RE_TAKEOFF = re.compile(
    r"^\s*take\s*off\s*to\s*([+-]?(?:\d+\.?\d*|\d*\.?\d+))\s*m\s*height\s*in\s*([+-]?(?:\d+\.?\d*|\d*\.?\d+))\s*seconds\s*$",
    re.IGNORECASE,
)
_RE_HOVER = re.compile(
    r"^\s*hover\s*at\s*([+-]?(?:\d+\.?\d*|\d*\.?\d+))\s*m\s*height\s*for\s*([+-]?(?:\d+\.?\d*|\d*\.?\d+))\s*seconds\s*$",
    re.IGNORECASE,
)
_RE_LAND = re.compile(
    r"^\s*land\s*from\s*([+-]?(?:\d+\.?\d*|\d*\.?\d+))\s*m\s*height\s*in\s*([+-]?(?:\d+\.?\d*|\d*\.?\d+))\s*seconds\s*$",
    re.IGNORECASE,
)
_RE_FLY = re.compile(
    r"^\s*fly\s*from\s*\(\s*([+-]?(?:\d+\.?\d*|\d*\.?\d+))\s*,\s*([+-]?(?:\d+\.?\d*|\d*\.?\d+))\s*,\s*([+-]?(?:\d+\.?\d*|\d*\.?\d+))\s*\)\s*"
    r"to\s*\(\s*([+-]?(?:\d+\.?\d*|\d*\.?\d+))\s*,\s*([+-]?(?:\d+\.?\d*|\d*\.?\d+))\s*,\s*([+-]?(?:\d+\.?\d*|\d*\.?\d+))\s*\)\s*"
    r"in\s*([+-]?(?:\d+\.?\d*|\d*\.?\d+))\s*seconds\s*$",
    re.IGNORECASE,
)


@dataclass
class _ParserState:
    t: float = 0.0
    pos: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    yaw: float = 0.0
    waypoints: List[List[float]] = field(default_factory=list)  # each [x,y,z,yaw]
    waypoint_times: List[float] = field(default_factory=list)
    modes: List[str] = field(default_factory=list)

    def _ensure_start(self) -> None:
        if not self.waypoints:
            self.waypoints.append([self.pos[0], self.pos[1], self.pos[2], self.yaw])
            self.waypoint_times.append(self.t)

    def _push_end(self, mode: str, dt: float, new_pos: Tuple[float, float, float]) -> None:
        self._ensure_start()
        self.t += float(dt)
        self.pos = [float(new_pos[0]), float(new_pos[1]), float(new_pos[2])]
        self.waypoints.append([self.pos[0], self.pos[1], self.pos[2], self.yaw])
        self.waypoint_times.append(self.t)
        self.modes.append(mode)


def parse_flight_plan(text: str) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Parse natural-language command(s) into (waypoints, times, modes).

    Returns:
      waypoints: (4, n) [x,y,z,yaw]
      waypoint_times: (n,) seconds
      modes: list length n-1 with one of {'takeoff','hover','fly','land'}
    """

    st = _ParserState()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        m = _RE_TAKEOFF.match(line)
        if m:
            h = float(m.group(1))
            dt = float(m.group(2))
            st.pos = [0.0, 0.0, 0.0] if not st.waypoints else st.pos
            st._ensure_start()
            st._push_end("takeoff", dt, (st.pos[0], st.pos[1], h))
            continue

        m = _RE_HOVER.match(line)
        if m:
            h = float(m.group(1))
            dt = float(m.group(2))
            if not st.waypoints:
                st.pos = [0.0, 0.0, h]
            st._ensure_start()
            st._push_end("hover", dt, (st.pos[0], st.pos[1], h))
            continue

        m = _RE_LAND.match(line)
        if m:
            h = float(m.group(1))
            dt = float(m.group(2))
            if not st.waypoints:
                st.pos = [0.0, 0.0, h]
            st._ensure_start()
            st._push_end("land", dt, (st.pos[0], st.pos[1], 0.0))
            continue

        m = _RE_FLY.match(line)
        if m:
            x0, y0, z0 = float(m.group(1)), float(m.group(2)), float(m.group(3))
            x1, y1, z1 = float(m.group(4)), float(m.group(5)), float(m.group(6))
            dt = float(m.group(7))
            if not st.waypoints:
                st.pos = [x0, y0, z0]
            st._ensure_start()
            st._push_end("fly", dt, (x1, y1, z1))
            continue

        raise ValueError(f"Unsupported command line: {raw_line!r}")

    waypoints = np.asarray(st.waypoints, dtype=float).T
    waypoint_times = np.asarray(st.waypoint_times, dtype=float)
    return waypoints, waypoint_times, st.modes
