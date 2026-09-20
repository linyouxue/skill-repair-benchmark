import numpy as np
from scipy.interpolate import CubicSpline


def _clamped_cubic(t0, t1, y0, y1):
    """Cubic spline over [t0, t1] with zero derivatives at both ends."""
    return CubicSpline([t0, t1], [y0, y1], bc_type=((1, 0.0), (1, 0.0)))


def trajectory_planner(waypoints, max_iter, waypoint_times, sample_rate, modes):
    """
    Build a (15 x max_iter) desired-state matrix by evaluating a per-segment
    cubic spline (with zero endpoint velocities) on each axis independently.
    Rows: 0:3 pos, 3:6 vel, 6:9 orient, 9:12 ang vel, 12:15 acc.
    """
    dt = 1.0 / sample_rate
    n_seg = len(modes)
    assert waypoints.shape[1] == n_seg + 1

    state = np.zeros((15, max_iter))

    # Precompute per-segment splines (x, y, z, yaw)
    seg_splines = []
    for s in range(n_seg):
        t0, t1 = waypoint_times[s], waypoint_times[s + 1]
        splines = []
        for axis in range(4):  # x, y, z, yaw
            y0 = waypoints[axis, s]
            y1 = waypoints[axis, s + 1]
            if modes[s] == 'hover':
                # constant position: build a trivial spline
                splines.append(CubicSpline([t0, t1], [y0, y0], bc_type=((1, 0.0), (1, 0.0))))
            else:
                splines.append(_clamped_cubic(t0, t1, y0, y1))
        seg_splines.append(splines)

    for k in range(max_iter):
        t = k * dt
        # find current segment
        if t <= waypoint_times[0]:
            s = 0
        elif t >= waypoint_times[-1]:
            s = n_seg - 1
            t = waypoint_times[-1]
        else:
            s = int(np.searchsorted(waypoint_times, t, side='right') - 1)
            s = min(max(s, 0), n_seg - 1)

        spx, spy, spz, spyaw = seg_splines[s]
        state[0, k] = spx(t)
        state[1, k] = spy(t)
        state[2, k] = spz(t)

        state[3, k] = spx(t, 1)
        state[4, k] = spy(t, 1)
        state[5, k] = spz(t, 1)

        state[8, k] = spyaw(t)          # yaw
        state[11, k] = spyaw(t, 1)      # yaw rate

        state[12, k] = spx(t, 2)
        state[13, k] = spy(t, 2)
        state[14, k] = spz(t, 2)

    return state


class WaypointTrajectory:
    """Callable that returns the next desired kinematic sample."""

    def __init__(self, waypoints, waypoint_times, sample_rate):
        self.dt = 1.0 / sample_rate
        self.t = float(waypoint_times[0])
        self.t_end = float(waypoint_times[-1])
        self.spx = CubicSpline(waypoint_times, waypoints[0], bc_type='clamped')
        self.spy = CubicSpline(waypoint_times, waypoints[1], bc_type='clamped')
        self.spz = CubicSpline(waypoint_times, waypoints[2], bc_type='clamped')
        self.spyaw = CubicSpline(waypoint_times, waypoints[3], bc_type='clamped')

    def __call__(self):
        t = min(self.t, self.t_end)
        pos = np.array([self.spx(t), self.spy(t), self.spz(t)])
        vel = np.array([self.spx(t, 1), self.spy(t, 1), self.spz(t, 1)])
        acc = np.array([self.spx(t, 2), self.spy(t, 2), self.spz(t, 2)])
        yaw = float(self.spyaw(t))
        self.t += self.dt
        return pos, yaw, vel, acc, np.zeros(3)
