import numpy as np


def build_prop_matrix(params: dict) -> np.ndarray:
    cT = float(params["thrust_coefficient"])
    cQ = float(params["moment_scale"])
    d = float(params["arm_length_effective"])

    return np.array(
        [
            [cT, cT, cT, cT],
            [0.0, d * cT, 0.0, -d * cT],
            [-d * cT, 0.0, d * cT, 0.0],
            [-cQ, cQ, -cQ, cQ],
        ],
        dtype=float,
    )


def motor_model(
    F_cmd: float, M_cmd: np.ndarray, motor_rpm: np.ndarray, params: dict, prop_matrix: np.ndarray
) -> tuple[float, np.ndarray, np.ndarray]:
    cmd = np.array([float(F_cmd), float(M_cmd[0]), float(M_cmd[1]), float(M_cmd[2])], dtype=float)

    rpm_sq_des = np.linalg.solve(prop_matrix, cmd)
    rpm_sq_des = np.clip(rpm_sq_des, 0.0, None)

    rpm_des = np.sqrt(rpm_sq_des)
    rpm_des = np.clip(rpm_des, float(params["rpm_min"]), float(params["rpm_max"]))

    km = float(params["motor_constant"])
    rpm_dot = km * (rpm_des - motor_rpm)

    fm = prop_matrix @ (motor_rpm**2)
    F_actual = float(fm[0])
    M_actual = np.array([fm[1], fm[2], fm[3]], dtype=float)

    return F_actual, M_actual, rpm_dot


def rotation_matrix_zyx(phi: float, theta: float, psi: float) -> np.ndarray:
    cphi, sphi = np.cos(phi), np.sin(phi)
    cth, sth = np.cos(theta), np.sin(theta)
    cps, sps = np.cos(psi), np.sin(psi)

    return np.array(
        [
            [cps * cth, cps * sth * sphi - sps * cphi, cps * sth * cphi + sps * sphi],
            [sps * cth, sps * sth * sphi + cps * cphi, sps * sth * cphi - cps * sphi],
            [-sth, cth * sphi, cth * cphi],
        ],
        dtype=float,
    )


def state_derivative(
    state: np.ndarray, F_cmd: float, M_cmd: np.ndarray, params: dict, prop_matrix: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    m = float(params["mass"])
    g = float(params["gravity"])

    pos = state[0:3]
    vel = state[3:6]
    rot = state[6:9]
    omega = state[9:12]
    motor_rpm = state[12:16]

    F_actual, M_actual, rpm_dot = motor_model(F_cmd, M_cmd, motor_rpm, params, prop_matrix)

    R = rotation_matrix_zyx(rot[0], rot[1], rot[2])
    thrust_world = (F_actual / m) * R[:, 2]
    acc_world = np.array([0.0, 0.0, -g], dtype=float) + thrust_world

    omega_dot = params["inertia_inv"] @ M_actual

    sd = np.zeros(16, dtype=float)
    sd[0:3] = vel
    sd[3:6] = acc_world
    sd[6:9] = omega
    sd[9:12] = omega_dot
    sd[12:16] = rpm_dot

    return sd, acc_world


def rk4_step(state: np.ndarray, F_cmd: float, M_cmd: np.ndarray, params: dict, prop_matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    dt = float(params["dt"])

    k1, acc0 = state_derivative(state, F_cmd, M_cmd, params, prop_matrix)
    k2, _ = state_derivative(state + 0.5 * dt * k1, F_cmd, M_cmd, params, prop_matrix)
    k3, _ = state_derivative(state + 0.5 * dt * k2, F_cmd, M_cmd, params, prop_matrix)
    k4, _ = state_derivative(state + dt * k3, F_cmd, M_cmd, params, prop_matrix)

    state_next = state + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)

    state_next[12:16] = np.clip(
        state_next[12:16], float(params["rpm_min"]), float(params["rpm_max"])
    )

    return state_next, acc0
