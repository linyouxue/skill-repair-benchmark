"""Position and attitude PID controllers plus the attitude planner."""

import numpy as np


class PositionPID:
    def __init__(self, kp, ki, kd, dt):
        self.kp = np.asarray(kp, dtype=float)
        self.ki = np.asarray(ki, dtype=float)
        self.kd = np.asarray(kd, dtype=float)
        self.dt = dt
        self.integral = np.zeros(3)

    def reset(self):
        self.integral = np.zeros(3)

    def __call__(self, pos_des, vel_des, acc_des, pos_cur, vel_cur):
        e = pos_des - pos_cur
        ed = vel_des - vel_cur
        self.integral += e * self.dt
        a_cmd = acc_des + self.kp * e + self.ki * self.integral + self.kd * ed
        return a_cmd


class AttitudePID:
    def __init__(self, kp, ki, kd, dt, inertia):
        self.kp = np.asarray(kp, dtype=float)
        self.ki = np.asarray(ki, dtype=float)
        self.kd = np.asarray(kd, dtype=float)
        self.dt = dt
        self.I = np.asarray(inertia, dtype=float)  # diagonal values
        self.integral = np.zeros(3)

    def reset(self):
        self.integral = np.zeros(3)

    def __call__(self, rot_des, omega_des, rot_cur, omega_cur):
        e = rot_des - rot_cur
        # yaw wrap
        e[2] = (e[2] + np.pi) % (2 * np.pi) - np.pi
        ed = omega_des - omega_cur
        self.integral += e * self.dt
        inner = self.kp * e + self.ki * self.integral + self.kd * ed
        M = self.I * inner  # diagonal inertia multiply
        return M


def attitude_planner(a_des, yaw_des, params):
    """Map desired lateral acceleration + yaw to desired roll/pitch.

    Small-angle approximation:
        phi_des   = ( ax sin(psi) - ay cos(psi) ) / g
        theta_des = ( ax cos(psi) + ay sin(psi) ) / g
    """
    g = params['gravity']
    psi = yaw_des
    ax, ay = a_des[0], a_des[1]
    phi_des = (ax * np.sin(psi) - ay * np.cos(psi)) / g
    theta_des = (ax * np.cos(psi) + ay * np.sin(psi)) / g
    # clamp aggressive tilt
    max_tilt = np.radians(30.0)
    phi_des = float(np.clip(phi_des, -max_tilt, max_tilt))
    theta_des = float(np.clip(theta_des, -max_tilt, max_tilt))
    return np.array([phi_des, theta_des, yaw_des])


def thrust_magnitude(a_des, params):
    """Tilt-compensated thrust: F = m * ||a_des + g e_z||."""
    g = params['gravity']
    m = params['mass']
    a_total = np.array([a_des[0], a_des[1], a_des[2] + g])
    return m * np.linalg.norm(a_total)
