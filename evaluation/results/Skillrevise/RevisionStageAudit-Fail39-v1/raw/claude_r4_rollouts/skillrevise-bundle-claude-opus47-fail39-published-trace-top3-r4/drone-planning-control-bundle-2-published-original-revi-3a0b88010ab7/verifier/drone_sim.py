"""Quadrotor closed-loop simulator: parser, planner, controllers, motor model, dynamics."""
import re
import numpy as np
import yaml
from scipy.integrate import solve_ivp


# ----------------------------- Parameters -----------------------------

def load_params(path="/root/system_params.yaml"):
    with open(path) as f:
        p = yaml.safe_load(f)
    p["dt"] = 1.0 / p["sample_rate"]
    p["I"] = np.diag(p["inertia"])
    p["I_inv"] = np.linalg.inv(p["I"])
    d = p["arm_length"] * np.sin(p["motor_spread_angle"])  # effective moment arm per axis
    cT = p["thrust_coefficient"]
    cQ = p["moment_scale"]
    # X-frame propeller allocation matrix: [F, Mx, My, Mz] = A @ rpm^2
    p["prop_matrix"] = np.array([
        [cT,     cT,     cT,     cT   ],
        [0.0,    d*cT,   0.0,   -d*cT ],
        [-d*cT,  0.0,    d*cT,   0.0  ],
        [-cQ,    cQ,    -cQ,     cQ   ],
    ])
    p["prop_matrix_inv"] = np.linalg.inv(p["prop_matrix"])
    return p


# ----------------------------- Flight Plan Parser -----------------------------

class FlightPlanParser:
    def __init__(self):
        self.waypoints = []           # list of [x,y,z,yaw]
        self.times = []
        self.modes = []
        self.pos = [0.0, 0.0, 0.0, 0.0]
        self.t = 0.0

    def _ensure_start(self):
        if not self.waypoints:
            self.waypoints.append(list(self.pos))
            self.times.append(self.t)

    def feed(self, line):
        s = line.strip()
        if not s:
            return
        m = re.match(r"take off to\s+([-\d.]+)\s*m.*in\s+([-\d.]+)\s*seconds?", s, re.I)
        if m:
            h, T = float(m.group(1)), float(m.group(2))
            self.pos = [0.0, 0.0, 0.0, 0.0]  # start on ground
            self._ensure_start()
            self.pos = [0.0, 0.0, h, 0.0]
            self.t += T
            self.waypoints.append(list(self.pos))
            self.times.append(self.t)
            self.modes.append("takeoff")
            return
        m = re.match(r"hover at\s+([-\d.]+)\s*m.*for\s+([-\d.]+)\s*seconds?", s, re.I)
        if m:
            h, T = float(m.group(1)), float(m.group(2))
            self.pos = [0.0, 0.0, h, 0.0]
            self._ensure_start()
            self.t += T
            self.waypoints.append(list(self.pos))
            self.times.append(self.t)
            self.modes.append("hover")
            return
        m = re.match(r"land from\s+([-\d.]+)\s*m.*in\s+([-\d.]+)\s*seconds?", s, re.I)
        if m:
            h, T = float(m.group(1)), float(m.group(2))
            self.pos = [0.0, 0.0, h, 0.0]
            self._ensure_start()
            self.pos = [0.0, 0.0, 0.0, 0.0]
            self.t += T
            self.waypoints.append(list(self.pos))
            self.times.append(self.t)
            self.modes.append("land")
            return
        m = re.match(
            r"fly from\s*\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)"
            r"\s*to\s*\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)"
            r"\s*in\s+([-\d.]+)\s*seconds?",
            s, re.I,
        )
        if m:
            x1, y1, z1, x2, y2, z2, T = map(float, m.groups())
            self.pos = [x1, y1, z1, 0.0]
            self._ensure_start()
            self.pos = [x2, y2, z2, 0.0]
            self.t += T
            self.waypoints.append(list(self.pos))
            self.times.append(self.t)
            self.modes.append("fly")
            return
        raise ValueError(f"Unrecognized command: {s!r}")

    def result(self):
        W = np.array(self.waypoints).T  # (4, n)
        T = np.array(self.times)
        return W, T, list(self.modes)


def parse_flight_plan(text):
    p = FlightPlanParser()
    for line in text.splitlines():
        p.feed(line)
    return p.result()


# ----------------------------- Trajectory Planner -----------------------------

def _quintic_coeffs(p0, pf, T):
    """Quintic polynomial with zero vel and accel at both endpoints."""
    # p(t) = p0 + (pf-p0) * s(tau), tau = t/T
    # s(tau) = 10 tau^3 - 15 tau^4 + 6 tau^5  (min-jerk)
    return p0, pf - p0, T


def _quintic_eval(c, t):
    p0, dp, T = c
    tau = np.clip(t / T, 0.0, 1.0)
    s   = 10 * tau**3 - 15 * tau**4 + 6 * tau**5
    sd  = (30 * tau**2 - 60 * tau**3 + 30 * tau**4) / T
    sdd = (60 * tau   - 180 * tau**2 + 120 * tau**3) / (T * T)
    return p0 + dp * s, dp * sd, dp * sdd


def plan_trajectory(waypoints, times, modes, dt):
    """Return (planned_state (15, N), time_vec (N,)) across all segments."""
    T_total = times[-1]
    N = int(round(T_total / dt)) + 1
    t_vec = np.arange(N) * dt
    state = np.zeros((15, N))

    for seg_idx, mode in enumerate(modes):
        t0, t1 = times[seg_idx], times[seg_idx + 1]
        p0 = waypoints[0:3, seg_idx]
        p1 = waypoints[0:3, seg_idx + 1]
        T = t1 - t0

        k0 = int(round(t0 / dt))
        k1 = int(round(t1 / dt))
        idx = np.arange(k0, k1 + 1)
        local_t = t_vec[idx] - t0

        if mode == "hover" or np.allclose(p0, p1):
            state[0:3, idx] = p0[:, None]
            state[3:6, idx] = 0.0
            state[12:15, idx] = 0.0
        else:
            c = [_quintic_coeffs(p0[i], p1[i], T) for i in range(3)]
            for i in range(3):
                p, v, a = _quintic_eval(c[i], local_t)
                state[i, idx]       = p
                state[3 + i, idx]   = v
                state[12 + i, idx]  = a
    return state, t_vec


# ----------------------------- Controllers -----------------------------

class PositionController:
    def __init__(self, kp, ki, kd, dt):
        self.kp = np.asarray(kp, float)
        self.ki = np.asarray(ki, float)
        self.kd = np.asarray(kd, float)
        self.dt = dt
        self.integ = np.zeros(3)

    def reset(self):
        self.integ[:] = 0.0

    def step(self, pos, vel, pos_des, vel_des, acc_ff):
        e = pos_des - pos
        edot = vel_des - vel
        self.integ += e * self.dt
        self.integ = np.clip(self.integ, -2.0, 2.0)
        return acc_ff + self.kp * e + self.kd * edot + self.ki * self.integ


class AttitudeController:
    def __init__(self, kp, ki, kd, dt):
        self.kp = np.asarray(kp, float)
        self.ki = np.asarray(ki, float)
        self.kd = np.asarray(kd, float)
        self.dt = dt
        self.integ = np.zeros(3)

    def reset(self):
        self.integ[:] = 0.0

    def step(self, euler, omega, euler_des, omega_des=None):
        if omega_des is None:
            omega_des = np.zeros(3)
        e = euler_des - euler
        # wrap yaw error
        e[2] = (e[2] + np.pi) % (2 * np.pi) - np.pi
        edot = omega_des - omega
        self.integ += e * self.dt
        self.integ = np.clip(self.integ, -1.0, 1.0)
        return self.kp * e + self.kd * edot + self.ki * self.integ


def attitude_planner(a_des, yaw_des, g=9.80665):
    """Map desired acceleration to desired roll, pitch, yaw."""
    ax, ay, az = a_des
    # thrust direction = a_des + g*e_z
    tz = az + g
    # Desired roll/pitch satisfy (small-angle or exact ZYX):
    #   ax = (sin yaw * sin phi + cos yaw * sin theta * cos phi) * tz / cos phi
    #   use exact: solve for phi, theta given tz, yaw
    cy, sy = np.cos(yaw_des), np.sin(yaw_des)
    # Rotated horizontal accel into yaw-aligned frame
    ax_b = cy * ax + sy * ay
    ay_b = -sy * ax + cy * ay
    phi_des = np.arctan2(-ay_b, np.sqrt(ax_b**2 + tz**2))
    theta_des = np.arctan2(ax_b, tz)
    return np.array([phi_des, theta_des, yaw_des])


# ----------------------------- Motor Model -----------------------------

def motor_step(params, F_cmd, M_cmd, rpm_current):
    """Given commanded thrust/moments and current motor RPMs, compute actual
    thrust/moments and RPM time-derivative."""
    desired = np.array([F_cmd, M_cmd[0], M_cmd[1], M_cmd[2]])
    rpm_sq_des = params["prop_matrix_inv"] @ desired
    rpm_sq_des = np.maximum(rpm_sq_des, 0.0)
    rpm_des = np.sqrt(rpm_sq_des)
    rpm_des = np.clip(rpm_des, params["rpm_min"], params["rpm_max"])
    rpm_dot = params["motor_constant"] * (rpm_des - rpm_current)
    return rpm_dot


def motor_forces(params, rpm):
    out = params["prop_matrix"] @ (rpm ** 2)
    return out[0], out[1:4]


# ----------------------------- Dynamics -----------------------------

def dynamics(params, state, F, M, rpm_dot):
    pos  = state[0:3]
    vel  = state[3:6]
    eul  = state[6:9]
    omg  = state[9:12]
    phi, theta, psi = eul
    m    = params["mass"]
    g    = params["gravity"]

    cphi, sphi = np.cos(phi), np.sin(phi)
    cth,  sth  = np.cos(theta), np.sin(theta)
    cps,  sps  = np.cos(psi), np.sin(psi)

    # Thrust in world frame (ZYX Euler, body +z)
    ax = (F / m) * (cps * sth * cphi + sps * sphi)
    ay = (F / m) * (sps * sth * cphi - cps * sphi)
    az = -g + (F / m) * (cth * cphi)

    # Euler-rate kinematics (ZYX, body omega -> euler rates)
    # [phi_dot; theta_dot; psi_dot] = W(eul) * omega
    # For moderate angles we can use the standard mapping:
    W = np.array([
        [1.0, sphi * np.tan(theta), cphi * np.tan(theta)],
        [0.0, cphi,                -sphi               ],
        [0.0, sphi / cth,           cphi / cth         ],
    ])
    eul_dot = W @ omg

    omg_dot = params["I_inv"] @ (M - np.cross(omg, params["I"] @ omg))

    ds = np.zeros(16)
    ds[0:3]   = vel
    ds[3:6]   = [ax, ay, az]
    ds[6:9]   = eul_dot
    ds[9:12]  = omg_dot
    ds[12:16] = rpm_dot
    return ds


def integrate_step(params, state16, F, M, rpm_dot, dt):
    def f(t, s):
        return dynamics(params, s, F, M, rpm_dot)
    sol = solve_ivp(f, (0.0, dt), state16, method="RK45",
                    rtol=1e-6, atol=1e-8, max_step=dt)
    return sol.y[:, -1]


# ----------------------------- Full Simulation Loop -----------------------------

def simulate(params, planned, gains, start_pos):
    """Run closed-loop sim. planned: (15, N). Returns actual (15, N)."""
    N = planned.shape[1]
    dt = params["dt"]
    m = params["mass"]
    g = params["gravity"]

    pos_ctrl = PositionController(gains["kp_pos"], gains["ki_pos"], gains["kd_pos"], dt)
    att_ctrl = AttitudeController(gains["kp_att"], gains["ki_att"], gains["kd_att"], dt)

    # Initial state: at start_pos, hover thrust rpm
    rpm_hover_sq = m * g / (4.0 * params["thrust_coefficient"])
    rpm_hover = np.sqrt(max(rpm_hover_sq, 0.0))
    rpm_hover = np.clip(rpm_hover, params["rpm_min"], params["rpm_max"])

    state16 = np.zeros(16)
    state16[0:3] = start_pos
    state16[12:16] = rpm_hover

    actual = np.zeros((15, N))
    prev_eul_des = None

    for k in range(N):
        pos = state16[0:3]
        vel = state16[3:6]
        eul = state16[6:9]
        omg = state16[9:12]
        rpm = state16[12:16]

        # Record state
        F_rec, M_rec = motor_forces(params, rpm)
        cphi, sphi = np.cos(eul[0]), np.sin(eul[0])
        cth,  sth  = np.cos(eul[1]), np.sin(eul[1])
        cps,  sps  = np.cos(eul[2]), np.sin(eul[2])
        acc_rec = np.array([
            (F_rec / m) * (cps * sth * cphi + sps * sphi),
            (F_rec / m) * (sps * sth * cphi - cps * sphi),
            -g + (F_rec / m) * (cth * cphi),
        ])
        actual[0:3, k]   = pos
        actual[3:6, k]   = vel
        actual[6:9, k]   = eul
        actual[9:12, k]  = omg
        actual[12:15, k] = acc_rec

        if k == N - 1:
            break

        # Reference
        pos_des = planned[0:3, k]
        vel_des = planned[3:6, k]
        acc_ff  = planned[12:15, k]

        # Position loop → desired acceleration
        a_des = pos_ctrl.step(pos, vel, pos_des, vel_des, acc_ff)

        # Thrust magnitude (tilt-compensated)
        thrust_vec = m * (a_des + np.array([0.0, 0.0, g]))
        F_cmd = np.linalg.norm(thrust_vec)

        # Attitude planner
        yaw_des = 0.0
        eul_des = attitude_planner(a_des, yaw_des, g)

        # Feed-forward angular rate from eul_des derivative
        if prev_eul_des is None:
            omega_ff = np.zeros(3)
        else:
            omega_ff = (eul_des - prev_eul_des) / dt
        prev_eul_des = eul_des

        # Attitude loop → body torques
        M_cmd = att_ctrl.step(eul, omg, eul_des, omega_ff)

        # Motor model
        rpm_dot = motor_step(params, F_cmd, M_cmd, rpm)
        F_act, M_act = motor_forces(params, rpm)

        # Integrate
        state16 = integrate_step(params, state16, F_act, M_act, rpm_dot, dt)

    return actual


# ----------------------------- Metrics -----------------------------

def stepinfo_3d(pos_actual, pos_target, t, settling_threshold=0.02):
    dist = np.linalg.norm(pos_actual - pos_target[:, None], axis=0)
    d0 = dist[0]
    if d0 < 1e-6:
        return {"RiseTime": 0.0, "SettlingTime": 0.0, "Overshoot_pct": 0.0,
                "SteadyStateError": float(dist[-1])}

    # Rise time: first index where dist <= 10% of d0
    rise_t = 0.0
    for k, d in enumerate(dist):
        if d <= 0.1 * d0:
            rise_t = float(t[k])
            break
    else:
        rise_t = float(t[-1])

    band = settling_threshold * d0
    settle_t = 0.0
    for k in range(len(dist) - 1, -1, -1):
        if dist[k] > band:
            settle_t = float(t[k])
            break

    # Overshoot: first time entering band, then max distance thereafter
    entered = np.where(dist <= band)[0]
    if len(entered) == 0:
        over_pct = 0.0
    else:
        k_enter = entered[0]
        if k_enter >= len(dist) - 1:
            over_pct = 0.0
        else:
            max_post = float(np.max(dist[k_enter:]))
            over_pct = max_post / d0 * 100.0

    return {"RiseTime": rise_t, "SettlingTime": settle_t,
            "Overshoot_pct": float(over_pct), "SteadyStateError": float(dist[-1])}
