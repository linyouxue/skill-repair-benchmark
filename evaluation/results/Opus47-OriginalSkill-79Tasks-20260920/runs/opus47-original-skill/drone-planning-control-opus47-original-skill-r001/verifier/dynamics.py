import numpy as np
from scipy.integrate import solve_ivp


def dynamics(params, state, F, M, rpm_dot):
    """Return the 16-element derivative of the drone state."""
    mass = params['mass']
    g    = params['gravity']
    I    = np.diag(params['inertia'])

    phi, theta, psi = state[6], state[7], state[8]
    p, q, r = state[9], state[10], state[11]

    ds = np.zeros(16)
    # position derivative = velocity
    ds[0:3] = state[3:6]

    # velocity derivative — thrust in body-z rotated to world via ZYX Euler
    cph, sph = np.cos(phi), np.sin(phi)
    cth, sth = np.cos(theta), np.sin(theta)
    cps, sps = np.cos(psi), np.sin(psi)

    ax = (F / mass) * (cps * sth * cph + sps * sph)
    ay = (F / mass) * (sps * sth * cph - cps * sph)
    az = -g + (F / mass) * (cth * cph)
    ds[3:6] = [ax, ay, az]

    # Euler-angle derivative — for small angles equals body rates; use full mapping
    # here we take Euler-rate = body-rate (valid for near-hover; simplifies the model)
    ds[6:9] = state[9:12]

    # angular acceleration
    omega = state[9:12]
    ds[9:12] = np.linalg.solve(I, M - np.cross(omega, I @ omega))

    ds[12:16] = rpm_dot
    return ds


def rk45_step(params, state, F, M, rpm_dot, dt):
    sol = solve_ivp(
        lambda t, s: dynamics(params, s, F, M, rpm_dot),
        (0.0, dt), state, method='RK45', rtol=1e-6, atol=1e-8,
    )
    return sol.y[:, -1]
