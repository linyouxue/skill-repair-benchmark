import re
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np


@dataclass
class FlightPlan:
    waypoints: np.ndarray  # (4, n) rows [x,y,z,yaw]
    waypoint_times: np.ndarray  # (n,)
    modes: List[str]  # (n-1)


_TAKEOFF_RE = re.compile(r"^\s*take\s+off\s+to\s+([0-9]*\.?[0-9]+)\s*m\s*height\s*in\s*([0-9]*\.?[0-9]+)\s*seconds\s*$", re.IGNORECASE)
_HOVER_RE = re.compile(r"^\s*hover\s+at\s+([0-9]*\.?[0-9]+)\s*m\s*height\s*for\s*([0-9]*\.?[0-9]+)\s*seconds\s*$", re.IGNORECASE)
_LAND_RE = re.compile(r"^\s*land\s+from\s+([0-9]*\.?[0-9]+)\s*m\s*height\s*in\s*([0-9]*\.?[0-9]+)\s*seconds\s*$", re.IGNORECASE)
_FLY_RE = re.compile(
    r"^\s*fly\s+from\s*\(\s*([+-]?[0-9]*\.?[0-9]+)\s*,\s*([+-]?[0-9]*\.?[0-9]+)\s*,\s*([+-]?[0-9]*\.?[0-9]+)\s*\)\s*"
    r"to\s*\(\s*([+-]?[0-9]*\.?[0-9]+)\s*,\s*([+-]?[0-9]*\.?[0-9]+)\s*,\s*([+-]?[0-9]*\.?[0-9]+)\s*\)\s*"
    r"in\s*([0-9]*\.?[0-9]+)\s*seconds\s*$",
    re.IGNORECASE,
)


def parse_flight_plan(text: str) -> FlightPlan:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise ValueError("Empty flight plan")

    waypoints: List[List[float]] = []
    times: List[float] = []
    modes: List[str] = []

    t_cur = 0.0
    for ln in lines:
        m = _TAKEOFF_RE.match(ln)
        if m:
            h = float(m.group(1))
            dur = float(m.group(2))
            if not waypoints:
                waypoints.append([0.0, 0.0, 0.0, 0.0])
                times.append(0.0)
            t_cur += dur
            waypoints.append([waypoints[-1][0], waypoints[-1][1], h, 0.0])
            times.append(t_cur)
            modes.append("takeoff")
            continue

        m = _HOVER_RE.match(ln)
        if m:
            h = float(m.group(1))
            dur = float(m.group(2))
            if not waypoints:
                waypoints.append([0.0, 0.0, h, 0.0])
                times.append(0.0)
            t_cur += dur
            waypoints.append([waypoints[-1][0], waypoints[-1][1], h, 0.0])
            times.append(t_cur)
            modes.append("hover")
            continue

        m = _LAND_RE.match(ln)
        if m:
            h = float(m.group(1))
            dur = float(m.group(2))
            if not waypoints:
                waypoints.append([0.0, 0.0, h, 0.0])
                times.append(0.0)
            t_cur += dur
            waypoints.append([waypoints[-1][0], waypoints[-1][1], 0.0, 0.0])
            times.append(t_cur)
            modes.append("land")
            continue

        m = _FLY_RE.match(ln)
        if m:
            x0, y0, z0, x1, y1, z1 = map(float, m.groups()[:6])
            dur = float(m.group(7))
            if not waypoints:
                waypoints.append([x0, y0, z0, 0.0])
                times.append(0.0)
            else:
                waypoints[-1][0:3] = [x0, y0, z0]
            t_cur += dur
            waypoints.append([x1, y1, z1, 0.0])
            times.append(t_cur)
            modes.append("fly")
            continue

        raise ValueError(f"Unrecognized command line: {ln!r}")

    wp = np.array(waypoints, dtype=float).T
    wt = np.array(times, dtype=float)
    if wp.shape[1] != wt.shape[0]:
        raise RuntimeError("Waypoint/time length mismatch")
    if len(modes) != wp.shape[1] - 1:
        raise RuntimeError("Mode count mismatch")

    return FlightPlan(waypoints=wp, waypoint_times=wt, modes=modes)
