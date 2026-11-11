import numpy as np


def rot_matrix_zyx(phi: float, theta: float, psi: float) -> np.ndarray:
    cphi, sphi = np.cos(phi), np.sin(phi)
    cth, sth = np.cos(theta), np.sin(theta)
    cps, sps = np.cos(psi), np.sin(psi)

    Rz = np.array([[cps, -sps, 0.0], [sps, cps, 0.0], [0.0, 0.0, 1.0]])
    Ry = np.array([[cth, 0.0, sth], [0.0, 1.0, 0.0], [-sth, 0.0, cth]])
    Rx = np.array([[1.0, 0.0, 0.0], [0.0, cphi, -sphi], [0.0, sphi, cphi]])
    return Rz @ Ry @ Rx


def dynamics(params: dict, state: np.ndarray, F: float, M: np.ndarray):
    m = float(params['mass'])
    g = float(params['gravity'])
    I = params['inertia_matrix']

    vel = state[3:6]
    rot = state[6:9]
    omega = state[9:12]

    phi, theta, psi = [float(x) for x in rot]
    R = rot_matrix_zyx(phi, theta, psi)
    thrust_dir = R @ np.array([0.0, 0.0, 1.0], dtype=float)

    acc = thrust_dir * (float(F) / m) + np.array([0.0, 0.0, -g], dtype=float)

    pos_dot = vel
    vel_dot = acc

    rot_dot = omega
    omega_dot = np.linalg.solve(I, M)

    state_dot = np.zeros_like(state)
    state_dot[0:3] = pos_dot
    state_dot[3:6] = vel_dot
    state_dot[6:9] = rot_dot
    state_dot[9:12] = omega_dot
    return state_dot
